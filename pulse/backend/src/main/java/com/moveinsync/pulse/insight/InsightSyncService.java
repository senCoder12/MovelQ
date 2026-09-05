package com.moveinsync.pulse.insight;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import com.moveinsync.pulse.agent.InsightAgentClient;
import com.moveinsync.pulse.agent.dto.Attribution;
import com.moveinsync.pulse.agent.dto.Control;
import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.agent.dto.Reference;
import com.moveinsync.pulse.agent.dto.TraceEntry;
import com.moveinsync.pulse.tenant.TenantContextHolder;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Pulls detected insights from the agent and persists them.
 *
 * <p>This is the seam between the two halves of the system. The agent owns DuckDB and
 * computes insights from it; the backend owns Postgres and serves them. Detection is a
 * warehouse scan measured in seconds, so it runs here on a refresh rather than on the path
 * of a user request -- the brief endpoint stays a single indexed read.
 *
 * <p>The write is an upsert keyed on {@code (tenant_id, insight_id)}, so a refresh updates
 * in place and the brief keeps working throughout. Child collections are replaced wholesale
 * rather than diffed: they have no stable identity of their own, and an insight's references
 * are only ever read together.
 *
 * <p>Only rows this service wrote are ever deleted. A metric that has recovered stops being
 * reported and its insight is retired; a seeded demo fixture is left alone, because the seed
 * is the fallback for when the agent is down.
 */
@Service
public class InsightSyncService {

    private static final Logger log = LoggerFactory.getLogger(InsightSyncService.class);

    private final InsightAgentClient agentClient;
    private final InsightRepository insights;
    private final BriefCache briefCache;

    public InsightSyncService(InsightAgentClient agentClient, InsightRepository insights, BriefCache briefCache) {
        this.agentClient = agentClient;
        this.insights = insights;
        this.briefCache = briefCache;
    }

    /** What a refresh did, so the caller can report it without re-querying. */
    public record SyncResult(String tenantId, int written, int retired) {
    }

    /** Tenants the agent can detect for.
     *
     * <p>The loop over these lives in {@link InsightRefreshRunner}, not here. Calling
     * {@link #sync} from another method of this class would be a self-invocation: it bypasses
     * the Spring proxy, so {@code @Transactional} would not apply and the first lazy child
     * collection touched would throw LazyInitializationException. Keeping the loop in a
     * different bean means every call goes through the proxy.
     */
    public List<String> tenants() {
        return agentClient.listTenants();
    }

    /**
     * Refreshes one tenant.
     *
     * <p>Transactional on purpose, unlike the read paths: this is many statements that only
     * make sense together, and a half-applied refresh would leave an insight whose
     * attribution belongs to the previous run.
     */
    @Transactional
    public SyncResult sync(String tenantId) {
        long startedAt = System.nanoTime();
        List<InsightPacket> packets = agentClient.listInsights(tenantId);

        Map<String, Insight> existing = new LinkedHashMap<>();
        for (Insight insight : insights.findAllBySource(Insight.SOURCE_AGENT)) {
            existing.put(insight.getInsightId(), insight);
        }

        List<Insight> toSave = new ArrayList<>();
        for (InsightPacket packet : packets) {
            Insight insight = existing.remove(packet.insightId());
            if (insight == null) {
                // findByInsightId, not findById: a seeded row may already hold this key, and
                // the unique constraint is on (tenant_id, insight_id).
                insight = insights.findByInsightId(packet.insightId())
                        .orElseGet(() -> new Insight(tenantId, packet.insightId()));
            }
            apply(packet, insight);
            toSave.add(insight);
        }
        insights.saveAll(toSave);

        // Whatever this service wrote last time and the agent no longer reports.
        List<Insight> retired = new ArrayList<>(existing.values());
        if (!retired.isEmpty()) {
            insights.deleteAll(retired);
        }

        briefCache.invalidate(tenantId);
        long elapsedMs = (System.nanoTime() - startedAt) / 1_000_000;
        log.info("insight sync for tenant {}: {} written, {} retired, {}ms",
                tenantId, toSave.size(), retired.size(), elapsedMs);
        return new SyncResult(tenantId, toSave.size(), retired.size());
    }

    /** Copies one packet onto an entity, replacing its children. */
    private static void apply(InsightPacket packet, Insight insight) {
        insight.setSource(Insight.SOURCE_AGENT);
        insight.setSeverity(clampSeverity(packet.severity()));

        insight.setMetricId(packet.metric().id());
        insight.setMetricName(packet.metric().name());
        insight.setMetricValue(packet.metric().value());
        insight.setMetricUnit(packet.metric().unit());
        insight.setMetricN(packet.metric().n());
        insight.setMetricWindow(packet.metric().window());

        insight.setEntityDim(packet.entity().dim());
        insight.setEntityRef(packet.entity().id());
        insight.setEntityName(packet.entity().name());

        insight.setImpactAffectedTrips(packet.impact() == null ? null : packet.impact().affectedTrips());
        insight.setImpactLateMinutesTotal(packet.impact() == null ? null : packet.impact().lateMinutesTotal());
        insight.setImpactCostInrMonth(packet.impact() == null ? null : packet.impact().costInrMonth());

        insight.setDataQualityExcludedPct(packet.dataQuality().excludedPct());
        insight.setDataQualityConfidence(packet.dataQuality().confidence());

        insight.setNarrativeHeadline(packet.narrative().headline());
        insight.setNarrativeBody(packet.narrative().body());
        insight.setRecommendedActions(orEmpty(packet.narrative().recommendedActions()));
        insight.setCoincidentEvents(orEmpty(packet.coincidentEvents()));

        insight.clearChildren();
        for (Reference reference : orEmpty(packet.references())) {
            insight.addReference(new InsightReference(
                    reference.type(), reference.label(), reference.value(), reference.unit()));
        }
        for (Attribution attribution : orEmpty(packet.attribution())) {
            insight.addAttribution(new InsightAttribution(
                    attribution.dim(), attribution.value(), attribution.contributionPct(), attribution.n()));
        }
        for (Control control : orEmpty(packet.controls())) {
            insight.addControl(new InsightControl(control.control(), control.gapPp(), control.survives()));
        }
        for (TraceEntry entry : orEmpty(packet.trace())) {
            insight.addTrace(new InsightTrace(
                    entry.queryId(),
                    entry.params(),
                    entry.numerator(),
                    entry.denominator(),
                    entry.exclusions(),
                    entry.validation() == null ? "pass" : entry.validation().status(),
                    entry.validation() == null ? null : entry.validation().notes()));
        }
    }

    /** ck_insight_severity is 0-100. A packet outside that is a bug upstream, but it must
     * not become a constraint violation that fails the whole refresh. */
    private static int clampSeverity(int severity) {
        return Math.max(0, Math.min(100, severity));
    }

    private static <T> List<T> orEmpty(List<T> values) {
        return values == null ? List.of() : values;
    }

    public Optional<Insight> find(String insightId) {
        return insights.findByInsightId(insightId);
    }
}
