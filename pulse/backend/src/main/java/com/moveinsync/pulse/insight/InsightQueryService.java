package com.moveinsync.pulse.insight;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import com.moveinsync.pulse.agent.dto.Attribution;
import com.moveinsync.pulse.agent.dto.CoincidentEvent;
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

import org.springframework.stereotype.Service;

/**
 * Reads insights out of Postgres and rebuilds them into the contract shape the API serves.
 *
 * <p>The read is a single wide query per call. Rows arrive as the cartesian product of an
 * insight and its three child collections, and this class folds them back -- one packet per
 * insight, children deduplicated by ordinal and kept in ordinal order. That is the whole
 * reason for the projection: from India, four small queries cost four round trips to
 * us-east-2, and the brief has a latency budget measured in hundreds of milliseconds.
 *
 * <p>Deliberately not {@code @Transactional}. A read-only transaction around a single
 * statement buys nothing here and costs a COMMIT round trip -- ~300ms at this distance.
 * {@link com.moveinsync.pulse.tenant.TenantFilterAspect} binds the session these methods
 * run on, so the tenant filter still applies.
 */
@Service
public class InsightQueryService implements InsightSource {

    private final InsightRepository insights;
    private final InsightTraceRepository traces;

    public InsightQueryService(InsightRepository insights, InsightTraceRepository traces) {
        this.insights = insights;
        this.traces = traces;
    }

    /** The brief feed: every insight for the tenant in context, worst first, trace omitted. */
    @Override
    public List<InsightPacket> listInsights() {
        return fold(insights.findBriefRows(), Map.of());
    }

    /** One insight, with its trace. Two queries rather than one: the trace is a drill-down,
     * and folding it into the brief projection would widen the product for every caller. */
    public Optional<InsightPacket> findInsight(String insightId) {
        List<BriefRow> rows = insights.findBriefRowsByInsightId(insightId);
        if (rows.isEmpty()) {
            return Optional.empty();
        }
        List<TraceEntry> trace = findTrace(insightId);
        return fold(rows, Map.of(insightId, trace)).stream().findFirst();
    }

    public List<TraceEntry> findTrace(String insightId) {
        return traces.findByInsightId(insightId).stream().map(InsightTrace::toDto).toList();
    }

    /** Folds the cartesian rows back into one packet per insight. */
    private static List<InsightPacket> fold(List<BriefRow> rows, Map<String, List<TraceEntry>> traceByInsightId) {
        Map<String, Accumulator> byInsightId = new LinkedHashMap<>();
        for (BriefRow row : rows) {
            byInsightId.computeIfAbsent(row.insightId(), key -> new Accumulator(row)).add(row);
        }
        return byInsightId.values().stream()
                .map(accumulator -> accumulator.toPacket(
                        traceByInsightId.getOrDefault(accumulator.head.insightId(), List.of())))
                .toList();
    }

    /** Collects the distinct children of one insight across its duplicated rows.
     * Ordinal is the dedup key -- ordinals are unique per insight per collection, and the
     * query already returns them in order. */
    private static final class Accumulator {

        private final BriefRow head;
        private final Map<Integer, Reference> references = new LinkedHashMap<>();
        private final Map<Integer, Attribution> attributions = new LinkedHashMap<>();
        private final Map<Integer, Control> controls = new LinkedHashMap<>();
        private final Set<Integer> seenReferenceOrdinals = new LinkedHashSet<>();

        private Accumulator(BriefRow head) {
            this.head = head;
        }

        private void add(BriefRow row) {
            if (row.referenceOrdinal() != null && seenReferenceOrdinals.add(row.referenceOrdinal())) {
                references.put(row.referenceOrdinal(), new Reference(
                        row.referenceType(),
                        row.referenceLabel(),
                        row.referenceValueNum() != null ? row.referenceValueNum() : row.referenceValueText(),
                        row.referenceUnit()));
            }
            if (row.attributionOrdinal() != null) {
                attributions.putIfAbsent(row.attributionOrdinal(), new Attribution(
                        row.attributionDim(), row.attributionValue(),
                        orZero(row.attributionContributionPct()), orZero(row.attributionN())));
            }
            if (row.controlOrdinal() != null) {
                controls.putIfAbsent(row.controlOrdinal(), new Control(
                        row.controlName(), orZero(row.controlGapPp()), Boolean.TRUE.equals(row.controlSurvives())));
            }
        }

        private InsightPacket toPacket(List<TraceEntry> trace) {
            List<RecommendedAction> recommendedActions =
                    head.recommendedActions() == null ? List.of() : head.recommendedActions();
            List<CoincidentEvent> coincidentEvents =
                    head.coincidentEvents() == null ? List.of() : head.coincidentEvents();
            return new InsightPacket(
                    head.insightId(),
                    new Metric(head.metricId(), head.metricName(), orZero(head.metricValue()), head.metricUnit(),
                            orZero(head.metricN()), head.metricWindow()),
                    new InsightEntity(head.entityDim(), head.entityRef(), head.entityName()),
                    new ArrayList<>(references.values()),
                    new ArrayList<>(attributions.values()),
                    new ArrayList<>(controls.values()),
                    coincidentEvents,
                    new Impact(head.impactAffectedTrips(), head.impactLateMinutesTotal(), head.impactCostInrMonth()),
                    new DataQuality(orZero(head.dataQualityExcludedPct()), head.dataQualityConfidence()),
                    orZero(head.severity()),
                    trace,
                    new Narrative(head.narrativeHeadline(), head.narrativeBody(), recommendedActions));
        }

        private static double orZero(Double value) {
            return value == null ? 0.0 : value;
        }

        private static int orZero(Integer value) {
            return value == null ? 0 : value;
        }
    }
}
