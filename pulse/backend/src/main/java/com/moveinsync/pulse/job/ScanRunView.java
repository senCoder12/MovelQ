package com.moveinsync.pulse.job;

import java.time.Duration;
import java.time.Instant;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/** One row of GET /api/jobs/status. `durationMs` is null while a run is
 * still in flight (finishedAt not yet set) -- the UI shows "running", not
 * a bogus zero-length duration. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record ScanRunView(
        @JsonProperty("scan_run_id") String scanRunId,
        @JsonProperty("started_at") Instant startedAt,
        @JsonProperty("finished_at") Instant finishedAt,
        @JsonProperty("duration_ms") Long durationMs,
        ScanRunStatus status,
        @JsonProperty("insight_count") int insightCount,
        @JsonProperty("alerts_fired") int alertsFired,
        @JsonProperty("alerts_suppressed") int alertsSuppressed,
        @JsonProperty("alerts_repeated") int alertsRepeated,
        @JsonProperty("error_summary") String errorSummary) {

    public static ScanRunView of(ScanRun run) {
        Long durationMs = run.finishedAt() == null
                ? null
                : Duration.between(run.startedAt(), run.finishedAt()).toMillis();
        return new ScanRunView(run.scanRunId(), run.startedAt(), run.finishedAt(), durationMs, run.status(),
                run.insightCount(), run.alertsFired(), run.alertsSuppressed(), run.alertsRepeated(),
                run.errorSummary());
    }
}
