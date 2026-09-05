package com.moveinsync.pulse.insight;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

/**
 * Insight persistence.
 *
 * <p>Every method here runs under the {@code tenantFilter} that
 * {@link com.moveinsync.pulse.tenant.TenantFilterAspect} enables, and a call with no tenant
 * in context throws rather than returning everything.
 *
 * <p>{@code findById} is overridden with an explicit query on purpose: Hibernate filters do
 * not apply to {@code EntityManager.find()}, so the inherited primary-key lookup would
 * happily hand back another tenant's insight. A query goes through the filter.
 */
public interface InsightRepository extends JpaRepository<Insight, Long> {

    @Override
    @Query("select i from Insight i where i.id = :id")
    Optional<Insight> findById(@Param("id") Long id);

    @Query("select i from Insight i where i.insightId = :insightId")
    Optional<Insight> findByInsightId(@Param("insightId") String insightId);

    /**
     * The whole brief in one round trip: insight plus references, attributions and controls.
     * Trace is deliberately absent -- it is a drill-down the UI fetches per insight from
     * /api/insights/{id}/trace, and pulling it in here would widen the product for data
     * nobody has asked for yet.
     */
    @Query("""
            select new com.moveinsync.pulse.insight.BriefRow(
                i.id, i.insightId, i.severity,
                i.metricId, i.metricName, i.metricValue, i.metricUnit, i.metricN, i.metricWindow,
                i.entityDim, i.entityRef, i.entityName,
                i.impactAffectedTrips, i.impactLateMinutesTotal, i.impactCostInrMonth,
                i.dataQualityExcludedPct, i.dataQualityConfidence,
                i.narrativeHeadline, i.narrativeBody, i.recommendedActions, i.coincidentEvents,
                r.refType, r.label, r.valueNum, r.valueText, r.unit, r.ordinal,
                a.dim, a.value, a.contributionPct, a.n, a.ordinal,
                c.control, c.gapPp, c.survives, c.ordinal)
            from Insight i
            left join i.references r
            left join i.attributions a
            left join i.controls c
            order by i.severity desc, i.insightId asc, r.ordinal asc, a.ordinal asc, c.ordinal asc
            """)
    List<BriefRow> findBriefRows();

    /** Same shape as the brief, narrowed to one insight. Still one round trip. */
    @Query("""
            select new com.moveinsync.pulse.insight.BriefRow(
                i.id, i.insightId, i.severity,
                i.metricId, i.metricName, i.metricValue, i.metricUnit, i.metricN, i.metricWindow,
                i.entityDim, i.entityRef, i.entityName,
                i.impactAffectedTrips, i.impactLateMinutesTotal, i.impactCostInrMonth,
                i.dataQualityExcludedPct, i.dataQualityConfidence,
                i.narrativeHeadline, i.narrativeBody, i.recommendedActions, i.coincidentEvents,
                r.refType, r.label, r.valueNum, r.valueText, r.unit, r.ordinal,
                a.dim, a.value, a.contributionPct, a.n, a.ordinal,
                c.control, c.gapPp, c.survives, c.ordinal)
            from Insight i
            left join i.references r
            left join i.attributions a
            left join i.controls c
            where i.insightId = :insightId
            order by r.ordinal asc, a.ordinal asc, c.ordinal asc
            """)
    List<BriefRow> findBriefRowsByInsightId(@Param("insightId") String insightId);

    boolean existsByInsightId(String insightId);

    /** Everything the sync wrote for this tenant, so it can retire what the agent no
     * longer reports without touching seeded rows. */
    @Query("select i from Insight i where i.source = :source")
    List<Insight> findAllBySource(@Param("source") String source);
}
