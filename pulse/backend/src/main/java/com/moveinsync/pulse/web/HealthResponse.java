package com.moveinsync.pulse.web;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Health of the three things Pulse depends on, reported separately so a failure names itself
 * instead of collapsing into one red dot.
 *
 * <p>{@code status} is UP only when all three are healthy, and DEGRADED otherwise -- the
 * application deliberately starts and serves this endpoint even when Neon is asleep.
 */
public record HealthResponse(
        String status,
        String service,
        String version,
        @JsonProperty("platform_db") PlatformDb platformDb,
        Agent agent,
        Warehouse warehouse) {

    public static final String UP = "UP";
    public static final String DEGRADED = "DEGRADED";

    /** Neon. {@code latencyMs} is a measured round trip, not a timeout budget: from India to
     * us-east-2 a healthy number is 150-250ms, and a cold start after Neon suspends the
     * branch can be several seconds without anything being wrong. */
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record PlatformDb(
            boolean reachable,
            @JsonProperty("latency_ms") Long latencyMs,
            @JsonProperty("server_version") String serverVersion,
            @JsonProperty("migration_version") String migrationVersion,
            String error) {

        public static PlatformDb up(long latencyMs, String serverVersion, String migrationVersion) {
            return new PlatformDb(true, latencyMs, serverVersion, migrationVersion, null);
        }

        public static PlatformDb down(long latencyMs, String error) {
            return new PlatformDb(false, latencyMs, null, null, error);
        }
    }

    /** The Python agent. {@code status} is kept at this shape because the shell reads it. */
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record Agent(boolean reachable, String status, String service, String version) {
    }

    /** The DuckDB analytical warehouse. Presence and readability only -- the backend does not
     * open it, the agent does. */
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record Warehouse(
            boolean present,
            boolean readable,
            String path,
            @JsonProperty("size_bytes") Long sizeBytes,
            String error) {
    }
}
