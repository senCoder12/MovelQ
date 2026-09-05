package com.moveinsync.pulse.action.dto;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Matches agent/app/actions/drafters.py's draft_action() return shape --
 * the agent's only output for an action, before Java ever persists it. */
public record AgentActionDraftResponse(
        @JsonProperty("action_id") String actionId,
        @JsonProperty("insight_id") String insightId,
        String type,
        String title,
        Recipient recipient,
        String channel,
        String subject,
        String body,
        @JsonProperty("facts_cited") List<FactCited> factsCited,
        Preview preview,
        String rationale,
        String confidence) {
}
