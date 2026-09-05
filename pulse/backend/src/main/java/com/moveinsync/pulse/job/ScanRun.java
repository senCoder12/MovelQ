package com.moveinsync.pulse.job;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** One run of the (minimal, on-demand) scan: not operational paging, just
 * the record a scan leaves of itself -- see ScanService's class docstring
 * for what actually happens during a run, and JobController for the
 * GET /api/jobs/status surface this feeds. */
@Entity
@Table(name = "scan_run")
public class ScanRun {

    @Id
    @Column(name = "scan_run_id", nullable = false, updatable = false, length = 64)
    private String scanRunId;

    @Column(name = "tenant_id", nullable = false, updatable = false, length = 64)
    private String tenantId;

    @Column(name = "started_at", nullable = false, updatable = false)
    private Instant startedAt;

    @Column(name = "finished_at")
    private Instant finishedAt;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 16)
    private ScanRunStatus status;

    @Column(name = "insight_count", nullable = false)
    private int insightCount;

    @Column(name = "alerts_fired", nullable = false)
    private int alertsFired;

    @Column(name = "alerts_suppressed", nullable = false)
    private int alertsSuppressed;

    @Column(name = "alerts_repeated", nullable = false)
    private int alertsRepeated;

    @Column(name = "error_summary", length = 2000)
    private String errorSummary;

    protected ScanRun() {
        // JPA
    }

    public ScanRun(String scanRunId, String tenantId, Instant startedAt) {
        this.scanRunId = scanRunId;
        this.tenantId = tenantId;
        this.startedAt = startedAt;
        this.status = ScanRunStatus.PARTIAL;
        this.insightCount = 0;
        this.alertsFired = 0;
        this.alertsSuppressed = 0;
        this.alertsRepeated = 0;
    }

    public void complete(ScanRunStatus status, Instant finishedAt, int insightCount, int alertsFired,
            int alertsSuppressed, int alertsRepeated, String errorSummary) {
        this.status = status;
        this.finishedAt = finishedAt;
        this.insightCount = insightCount;
        this.alertsFired = alertsFired;
        this.alertsSuppressed = alertsSuppressed;
        this.alertsRepeated = alertsRepeated;
        this.errorSummary = errorSummary;
    }

    public String scanRunId() {
        return scanRunId;
    }

    public String tenantId() {
        return tenantId;
    }

    public Instant startedAt() {
        return startedAt;
    }

    public Instant finishedAt() {
        return finishedAt;
    }

    public ScanRunStatus status() {
        return status;
    }

    public int insightCount() {
        return insightCount;
    }

    public int alertsFired() {
        return alertsFired;
    }

    public int alertsSuppressed() {
        return alertsSuppressed;
    }

    public int alertsRepeated() {
        return alertsRepeated;
    }

    public String errorSummary() {
        return errorSummary;
    }
}
