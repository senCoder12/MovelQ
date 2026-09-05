package com.moveinsync.pulse.report;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Body returned by the agent's POST /internal/leadership-narrative: the
 * prose fields only. Merged onto the structured LeadershipPack by
 * LeadershipPackService, matched by insight_id. */
public record LeadershipNarrativeResponse(String headline, String summary, List<FindingNarrative> findings) {

    public record FindingNarrative(
            @JsonProperty("insight_id") String insightId,
            String body,
            String recommendation) {
    }
}
