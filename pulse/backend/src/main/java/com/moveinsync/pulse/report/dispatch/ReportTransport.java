package com.moveinsync.pulse.report.dispatch;

/** The only interface a report is ever transmitted through. Every caller
 * (ReportDispatchService) depends on this type alone -- never on
 * LoggedTransport or SmtpTransport directly -- so which one is active is a
 * config change (pulse.dispatch.transport), never a code change. Exactly one
 * implementation is ever active in a given running instance: each is
 * conditional on that same property, so Spring has exactly one
 * ReportTransport bean to inject regardless of which value it is set to. */
public interface ReportTransport {

    DispatchResult send(DispatchRequest request);

    /** "logged" or "smtp" -- stored on report_dispatch.transport and echoed
     * to the frontend so it can label its confirm button honestly. */
    String name();
}
