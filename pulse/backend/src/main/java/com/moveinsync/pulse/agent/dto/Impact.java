package com.moveinsync.pulse.agent.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/** Matches contracts/insight.schema.json $defs.impact. Every field is optional -- @JsonInclude
 * keeps a field the agent didn't populate out of the response entirely (not serialized as
 * null), so the frontend's "only render keys that are present" check still works. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record Impact(
        @JsonProperty("affected_trips") Integer affectedTrips,
        @JsonProperty("late_minutes_total") Double lateMinutesTotal,
        @JsonProperty("cost_inr_month") Double costInrMonth) {
}
