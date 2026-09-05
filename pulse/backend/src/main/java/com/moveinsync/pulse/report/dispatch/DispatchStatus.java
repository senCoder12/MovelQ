package com.moveinsync.pulse.report.dispatch;

/** Outcome of one ReportTransport.send() call. There is no PENDING/QUEUED
 * state -- both transports today are synchronous, so a dispatch is either
 * SUCCESS or FAILED by the time send() returns. */
public enum DispatchStatus {
    SUCCESS,
    FAILED
}
