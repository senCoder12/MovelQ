package com.moveinsync.pulse.web;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.moveinsync.pulse.agent.dto.DataQuality;

/** Matches contracts/openapi.yaml components.schemas.DataQualityResponse. */
public record DataQualityResponse(List<Entry> entries) {

    public record Entry(
            @JsonProperty("insight_id") String insightId,
            @JsonProperty("metric_id") String metricId,
            @JsonProperty("data_quality") DataQuality dataQuality) {
    }
}
