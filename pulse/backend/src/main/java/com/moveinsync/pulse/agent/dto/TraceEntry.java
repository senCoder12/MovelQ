package com.moveinsync.pulse.agent.dto;

import java.util.Map;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Matches contracts/insight.schema.json $defs.trace_entry. */
public record TraceEntry(
        @JsonProperty("query_id") String queryId,
        Map<String, Object> params,
        int numerator,
        int denominator,
        java.util.List<String> exclusions,
        Validation validation) {
}
