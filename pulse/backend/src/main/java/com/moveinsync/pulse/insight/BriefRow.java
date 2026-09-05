package com.moveinsync.pulse.insight;

import java.util.List;

import com.moveinsync.pulse.agent.dto.CoincidentEvent;
import com.moveinsync.pulse.agent.dto.RecommendedAction;

/**
 * One flat row of the brief query: an insight joined against one of its references, one of
 * its attributions and one of its controls.
 *
 * <p>The join is a cartesian product per insight (refs x attributions x controls), so the
 * same insight arrives several times and {@link InsightQueryService} folds the duplicates
 * back into one packet. That trade is deliberate: from India to us-east-2 each round trip
 * costs 150-250ms, so one wide result beats four tidy ones. It holds because these
 * collections are single digits per insight. If any of them ever grows into the hundreds,
 * split the query rather than letting the product grow.
 *
 * <p>Every child column is a wrapper type -- an insight with no controls still produces a
 * row, with nulls in the control columns.
 */
public record BriefRow(
        Long id,
        String insightId,
        Integer severity,
        String metricId,
        String metricName,
        Double metricValue,
        String metricUnit,
        Integer metricN,
        String metricWindow,
        String entityDim,
        String entityRef,
        String entityName,
        Integer impactAffectedTrips,
        Double impactLateMinutesTotal,
        Double impactCostInrMonth,
        Double dataQualityExcludedPct,
        String dataQualityConfidence,
        String narrativeHeadline,
        String narrativeBody,
        List<RecommendedAction> recommendedActions,
        List<CoincidentEvent> coincidentEvents,

        String referenceType,
        String referenceLabel,
        Double referenceValueNum,
        String referenceValueText,
        String referenceUnit,
        Integer referenceOrdinal,

        String attributionDim,
        String attributionValue,
        Double attributionContributionPct,
        Integer attributionN,
        Integer attributionOrdinal,

        String controlName,
        Double controlGapPp,
        Boolean controlSurvives,
        Integer controlOrdinal) {
}
