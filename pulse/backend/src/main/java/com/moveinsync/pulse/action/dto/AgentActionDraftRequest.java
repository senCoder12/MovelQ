package com.moveinsync.pulse.action.dto;

import com.moveinsync.pulse.agent.dto.InsightPacket;

/** Body posted to the agent's POST /internal/draft-action. Java always
 * forwards the full InsightPacket it already fetched -- same shape as
 * LeadershipNarrativeRequest -- so the agent stays a pure function of the
 * packet it is given rather than needing its own lookup-by-id store. */
public record AgentActionDraftRequest(InsightPacket insight, String type) {
}
