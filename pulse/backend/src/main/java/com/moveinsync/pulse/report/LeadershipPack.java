package com.moveinsync.pulse.report;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

/** One-click monthly report for a transport & facilities head to forward to
 * leadership unedited. Matches contracts/openapi.yaml components.schemas.LeadershipPack. */
public record LeadershipPack(
        String period,
        Scope scope,
        String headline,
        String summary,
        List<Tile> tiles,
        List<Finding> findings,
        Footer footer) {

    public record Scope(
            String tenant,
            List<String> sites,
            @JsonProperty("trip_count") int tripCount,
            @JsonProperty("date_range") DateRange dateRange) {
    }

    public record DateRange(String from, String to) {
    }

    /** value/reference are pre-formatted display strings ("215,885", "45.5%") -- the
     * document renders them verbatim, it does not reformat numbers itself. */
    public record Tile(String label, String value, String reference, Direction direction) {
    }

    public enum Direction {
        @JsonProperty("good") GOOD,
        @JsonProperty("bad") BAD,
        @JsonProperty("neutral") NEUTRAL
    }

    public record Finding(
            String title,
            int severity,
            String body,
            String recommendation,
            @JsonProperty("insight_id") String insightId) {
    }

    public record Footer(
            @JsonProperty("computed_from_trips") int computedFromTrips,
            @JsonProperty("excluded_trips") int excludedTrips,
            @JsonProperty("excluded_pct") double excludedPct,
            @JsonProperty("exclusion_reasons") List<String> exclusionReasons) {
    }
}
