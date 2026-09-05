package com.moveinsync.pulse.insight;

import java.util.List;
import java.util.Map;

import com.moveinsync.pulse.agent.InsightAgentClient;
import com.moveinsync.pulse.agent.dto.Attribution;
import com.moveinsync.pulse.agent.dto.Control;
import com.moveinsync.pulse.agent.dto.DataQuality;
import com.moveinsync.pulse.agent.dto.Impact;
import com.moveinsync.pulse.agent.dto.InsightEntity;
import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.agent.dto.Metric;
import com.moveinsync.pulse.agent.dto.Narrative;
import com.moveinsync.pulse.agent.dto.RecommendedAction;
import com.moveinsync.pulse.agent.dto.Reference;
import com.moveinsync.pulse.agent.dto.TraceEntry;
import com.moveinsync.pulse.agent.dto.Validation;
import com.moveinsync.pulse.tenant.TenantContextHolder;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * The sync between agent-detected insights and Postgres.
 *
 * <p>The behaviour worth pinning is what it does on the *second* run: refresh in place, retire
 * what the agent has stopped reporting, and leave seeded rows alone. Getting that wrong is
 * either a dashboard that never forgets a resolved problem, or a demo whose fixtures vanish
 * the first time someone clicks refresh.
 */
@SpringBootTest
@Transactional
class InsightSyncServiceTest {

    private static final String TENANT = "catalyst";

    @Autowired
    private InsightRepository insights;

    @Autowired
    private BriefCache briefCache;

    @Autowired
    private JdbcTemplate jdbc;

    private InsightSyncService syncWith(List<InsightPacket> packets) {
        return new InsightSyncService(new FakeAgentClient(packets), insights, briefCache);
    }

    @BeforeEach
    void clearContext() {
        TenantContextHolder.set(TENANT);
        briefCache.invalidateAll();
    }

    @Test
    @DisplayName("a packet lands as an insight with its children and agent provenance")
    void writesPacketWithChildren() {
        syncWith(List.of(packet("sync_metric", 80, 12.5))).sync(TENANT);

        Insight stored = insights.findByInsightId("sync_metric").orElseThrow();
        assertThat(stored.getSource()).isEqualTo(Insight.SOURCE_AGENT);
        assertThat(stored.getTenantId()).isEqualTo(TENANT);
        assertThat(stored.getSeverity()).isEqualTo(80);
        assertThat(stored.getMetricValue()).isEqualTo(12.5);
        assertThat(stored.getReferences()).hasSize(1);
        assertThat(stored.getAttributions()).hasSize(1);
        assertThat(stored.getControls()).hasSize(1);
        assertThat(stored.getTraces()).hasSize(1);
        assertThat(stored.getRecommendedActions()).hasSize(1);
        assertThat(stored.getImpactCostInrMonth()).isEqualTo(4200.0);
    }

    @Test
    @DisplayName("re-syncing updates in place and does not duplicate children")
    void secondSyncUpdatesInPlace() {
        syncWith(List.of(packet("sync_metric", 80, 12.5))).sync(TENANT);
        Long firstId = insights.findByInsightId("sync_metric").orElseThrow().getId();

        InsightSyncService.SyncResult result = syncWith(List.of(packet("sync_metric", 91, 20.0))).sync(TENANT);

        assertThat(result.written()).isEqualTo(1);
        assertThat(result.retired()).isZero();
        Insight stored = insights.findByInsightId("sync_metric").orElseThrow();
        assertThat(stored.getId()).isEqualTo(firstId);
        assertThat(stored.getSeverity()).isEqualTo(91);
        assertThat(stored.getMetricValue()).isEqualTo(20.0);
        assertThat(stored.getReferences()).hasSize(1);
        assertThat(stored.getAttributions()).hasSize(1);
    }

    @Test
    @DisplayName("an insight the agent no longer reports is retired")
    void staleInsightIsRetired() {
        syncWith(List.of(packet("sync_gone", 70, 9.0), packet("sync_stays", 60, 8.0))).sync(TENANT);

        InsightSyncService.SyncResult result = syncWith(List.of(packet("sync_stays", 60, 8.0))).sync(TENANT);

        assertThat(result.retired()).isEqualTo(1);
        assertThat(insights.findByInsightId("sync_gone")).isEmpty();
        assertThat(insights.findByInsightId("sync_stays")).isPresent();
    }

    @Test
    @DisplayName("seeded insights survive a sync that does not mention them")
    void seededInsightsAreLeftAlone() {
        jdbc.update("""
                insert into insight (
                    tenant_id, insight_id, severity, source,
                    metric_id, metric_name, metric_value, metric_unit, metric_n, metric_window,
                    entity_dim, entity_ref, entity_name,
                    data_quality_excluded_pct, data_quality_confidence,
                    narrative_headline, narrative_body)
                values (?, 'sync_seeded', 40, 'seed', 'seed_metric', 'Seed metric', 1.0, '%', 1,
                        'trailing_30d', 'fleet', 'ALL', 'Fleet-wide', 0.0, 'high', 'seeded', 'fixture')
                """, TENANT);

        syncWith(List.of(packet("sync_metric", 80, 12.5))).sync(TENANT);

        Insight seeded = insights.findByInsightId("sync_seeded").orElseThrow();
        assertThat(seeded.getSource()).isEqualTo(Insight.SOURCE_SEED);
        assertThat(seeded.getSeverity()).isEqualTo(40);
    }

    @Test
    @DisplayName("a sync drops the tenant's cached brief so the next read is fresh")
    void syncInvalidatesTheBriefCache() {
        syncWith(List.of(packet("sync_metric", 80, 12.5))).sync(TENANT);
        List<InsightPacket> before = briefCache.insights();
        assertThat(before).extracting(InsightPacket::insightId).contains("sync_metric");

        syncWith(List.of(packet("sync_metric", 95, 30.0))).sync(TENANT);

        List<InsightPacket> after = briefCache.insights();
        assertThat(after).isNotSameAs(before);
        assertThat(after)
                .filteredOn(packet -> packet.insightId().equals("sync_metric"))
                .singleElement()
                .extracting(InsightPacket::severity)
                .isEqualTo(95);
    }

    @Test
    @DisplayName("a severity outside 0-100 is clamped rather than breaking the whole refresh")
    void severityIsClamped() {
        syncWith(List.of(packet("sync_metric", 4321, 12.5))).sync(TENANT);

        assertThat(insights.findByInsightId("sync_metric").orElseThrow().getSeverity()).isEqualTo(100);
    }

    private static InsightPacket packet(String insightId, int severity, double value) {
        return new InsightPacket(
                insightId,
                new Metric(insightId, "Metric " + insightId, value, "%", 1000, "2026-07-01..2026-07-31"),
                new InsightEntity("tenant", TENANT, TENANT),
                List.of(new Reference("sla", "target", 2.0, "percent")),
                List.of(new Attribution("vendor_id", "Acme Travel", 55.5, 120)),
                List.of(new Control("office", 3.2, true)),
                List.of(),
                new Impact(120, null, 4200.0),
                new DataQuality(0.5, "high"),
                severity,
                List.of(new TraceEntry("q1", Map.of("dim", "tenant_id"), 120, 1000, List.of("flagged rows"),
                        new Validation("pass", "reconciles"))),
                new Narrative("headline", "body",
                        List.of(new RecommendedAction("ticket", "title", "draft", "rationale"))));
    }

    /** Stands in for the agent so the sync's own logic is what is under test. */
    private static final class FakeAgentClient extends InsightAgentClient {

        private final List<InsightPacket> packets;

        FakeAgentClient(List<InsightPacket> packets) {
            super(null);
            this.packets = packets;
        }

        @Override
        public List<InsightPacket> listInsights(String tenantId) {
            return packets;
        }

        @Override
        public List<String> listTenants() {
            return List.of(TENANT);
        }
    }
}
