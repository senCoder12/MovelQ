package com.moveinsync.pulse.agent.dto;

/** Matches contracts/insight.schema.json $defs.recommended_action. */
public record RecommendedAction(String type, String title, String draft, String rationale) {
}
