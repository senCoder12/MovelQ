package com.moveinsync.pulse.agent.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Matches contracts/insight.schema.json $defs.data_quality. */
public record DataQuality(@JsonProperty("excluded_pct") double excludedPct, String confidence) {
}
