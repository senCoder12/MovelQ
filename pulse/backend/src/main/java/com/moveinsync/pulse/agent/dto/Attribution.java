package com.moveinsync.pulse.agent.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Matches contracts/insight.schema.json $defs.attribution. */
public record Attribution(String dim, String value, @JsonProperty("contribution_pct") double contributionPct, int n) {
}
