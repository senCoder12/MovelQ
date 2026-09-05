package com.moveinsync.pulse.action.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/** One entry in a draft's facts_cited block -- the trace equivalent for
 * actions. Every number quoted in an action's subject/body must appear here,
 * with the InsightPacket field it came from, so a reader can verify the
 * draft invented nothing. */
public record FactCited(String label, String value, @JsonProperty("source_field") String sourceField) {
}
