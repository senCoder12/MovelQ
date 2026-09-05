package com.moveinsync.pulse.tenant;

import java.util.List;

import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.insight.Insight;
import com.moveinsync.pulse.insight.InsightQueryService;
import com.moveinsync.pulse.insight.InsightRepository;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Proves tenant isolation is enforced by the data layer rather than by every caller
 * remembering to add a predicate.
 *
 * <p>Rows are inserted for two tenants through plain JDBC, deliberately bypassing every
 * application-level guard. The queries under test then run with no tenant predicate of their
 * own -- {@code findAll()}, {@code count()}, the brief projection -- and the assertions are
 * that the other tenant's rows are simply not there.
 *
 * <p>Needs a real Postgres: the schema uses JSONB, TIMESTAMPTZ and BIGSERIAL, and a test
 * against an in-memory imitation would prove nothing about what runs on Neon. Point
 * PULSE_DB_URL/USER/PASSWORD at a scratch database, or let it default to
 * localhost:5432/pulse_test. The test rolls back everything it writes.
 */
@SpringBootTest
@Transactional
class TenantIsolationTest {

    private static final String CATALYST = "catalyst";
    private static final String VANTA = "vanta";

    @Autowired
    private InsightRepository insights;

    @Autowired
    private InsightQueryService insightQueryService;

    @Autowired
    private JdbcTemplate jdbc;

    @BeforeEach
    void insertRowsForBothTenants() {
        TenantContextHolder.clear();
        insertInsight(CATALYST, "iso_catalyst_1", 90, "catalyst headline one");
        insertInsight(CATALYST, "iso_catalyst_2", 70, "catalyst headline two");
        insertInsight(VANTA, "iso_vanta_1", 95, "vanta headline one");
        insertInsight(VANTA, "iso_vanta_2", 80, "vanta headline two");
        // Same business key under both tenants -- if scoping leaked, this is what would collide.
        insertInsight(CATALYST, "iso_shared", 60, "catalyst shared-key headline");
        insertInsight(VANTA, "iso_shared", 61, "vanta shared-key headline");
    }

    @Test
    @DisplayName("a query with no tenant predicate returns no other tenant's rows")
    void queryWithoutTenantPredicateReturnsOnlyCurrentTenant() {
        TenantContextHolder.set(CATALYST);

        List<Insight> found = insights.findAll();

        assertThat(found).isNotEmpty();
        assertThat(found).extracting(Insight::getTenantId).containsOnly(CATALYST);
        assertThat(found).extracting(Insight::getTenantId).doesNotContain(VANTA);
        assertThat(found).extracting(Insight::getInsightId)
                .contains("iso_catalyst_1", "iso_catalyst_2", "iso_shared")
                .doesNotContain("iso_vanta_1", "iso_vanta_2");
    }

    @Test
    @DisplayName("the same business key resolves to the current tenant's row, not the other's")
    void sharedBusinessKeyResolvesPerTenant() {
        TenantContextHolder.set(CATALYST);
        assertThat(insights.findByInsightId("iso_shared"))
                .get()
                .extracting(Insight::getNarrativeHeadline)
                .isEqualTo("catalyst shared-key headline");

        TenantContextHolder.set(VANTA);
        assertThat(insights.findByInsightId("iso_shared"))
                .get()
                .extracting(Insight::getNarrativeHeadline)
                .isEqualTo("vanta shared-key headline");
    }

    @Test
    @DisplayName("count() is scoped, so aggregates cannot leak volumes either")
    void countIsScoped() {
        TenantContextHolder.set(CATALYST);
        long catalystCount = insights.count();

        TenantContextHolder.set(VANTA);
        long vantaCount = insights.count();

        long total = jdbc.queryForObject(
                "select count(*) from insight where tenant_id in (?, ?)", Long.class, CATALYST, VANTA);

        assertThat(catalystCount).isPositive();
        assertThat(vantaCount).isPositive();
        assertThat(catalystCount + vantaCount).isEqualTo(total);
    }

    @Test
    @DisplayName("a primary-key lookup cannot reach across tenants")
    void findByIdCannotCrossTenants() {
        Long vantaId = jdbc.queryForObject(
                "select id from insight where tenant_id = ? and insight_id = ?", Long.class, VANTA, "iso_vanta_1");

        TenantContextHolder.set(CATALYST);

        // Hibernate filters do not apply to EntityManager.find(), which is why
        // InsightRepository overrides findById with a query. This is that guard.
        assertThat(insights.findById(vantaId)).isEmpty();
    }

    @Test
    @DisplayName("the brief projection is scoped too, not just entity loads")
    void briefProjectionIsScoped() {
        TenantContextHolder.set(CATALYST);

        List<InsightPacket> packets = insightQueryService.listInsights();

        assertThat(packets).isNotEmpty();
        assertThat(packets).extracting(InsightPacket::insightId)
                .contains("iso_catalyst_1", "iso_catalyst_2")
                .doesNotContain("iso_vanta_1", "iso_vanta_2");
        assertThat(packets)
                .filteredOn(packet -> packet.insightId().equals("iso_shared"))
                .singleElement()
                .extracting(packet -> packet.narrative().headline())
                .isEqualTo("catalyst shared-key headline");
    }

    @Test
    @DisplayName("no tenant in context throws rather than returning everything")
    void repositoryCallWithoutTenantThrows() {
        TenantContextHolder.clear();

        assertThatThrownBy(() -> insights.findAll())
                .isInstanceOf(MissingTenantException.class)
                .hasMessageContaining("tenant-scoped");

        assertThatThrownBy(() -> insights.findByInsightId("iso_catalyst_1"))
                .isInstanceOf(MissingTenantException.class);

        assertThatThrownBy(() -> insightQueryService.listInsights())
                .isInstanceOf(MissingTenantException.class);
    }

    private void insertInsight(String tenantId, String insightId, int severity, String headline) {
        jdbc.update("""
                insert into insight (
                    tenant_id, insight_id, severity,
                    metric_id, metric_name, metric_value, metric_unit, metric_n, metric_window,
                    entity_dim, entity_ref, entity_name,
                    data_quality_excluded_pct, data_quality_confidence,
                    narrative_headline, narrative_body)
                values (?, ?, ?, 'iso_metric', 'Isolation metric', 1.0, '%', 1, 'trailing_30d',
                        'fleet', 'ALL', 'Fleet-wide', 0.0, 'high', ?, 'isolation fixture')
                """, tenantId, insightId, severity, headline);
    }
}
