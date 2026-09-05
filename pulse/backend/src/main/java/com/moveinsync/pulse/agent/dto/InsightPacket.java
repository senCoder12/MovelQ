package com.moveinsync.pulse.agent.dto;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Matches contracts/insight.schema.json (root). Typed 1:1 mirror of the agent's payload
 * -- no additional/derived fields, this is a passthrough shape. */
public record InsightPacket(
        @JsonProperty("insight_id") String insightId,
        Metric metric,
        InsightEntity entity,
        List<Reference> references,
        List<Attribution> attribution,
        List<Control> controls,
        @JsonProperty("coincident_events") List<CoincidentEvent> coincidentEvents,
        Impact impact,
        @JsonProperty("data_quality") DataQuality dataQuality,
        int severity,
        List<TraceEntry> trace,
        Narrative narrative) {
}
