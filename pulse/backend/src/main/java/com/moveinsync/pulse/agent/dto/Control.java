package com.moveinsync.pulse.agent.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Matches contracts/insight.schema.json $defs.control. */
public record Control(String control, @JsonProperty("gap_pp") double gapPp, boolean survives) {
}
