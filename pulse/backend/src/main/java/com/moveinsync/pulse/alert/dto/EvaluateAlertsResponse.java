package com.moveinsync.pulse.alert.dto;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

public record EvaluateAlertsResponse(
        List<AlertCandidate> candidates,
        @JsonProperty("ranked_insight_ids") List<String> rankedInsightIds) {
}
