package com.moveinsync.pulse.agent.dto;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Matches contracts/openapi.yaml components.schemas.TraceResponse. */
public record TraceResponse(@JsonProperty("insight_id") String insightId, List<TraceEntry> trace) {
}
