package com.moveinsync.pulse.report.dispatch;

/** A recipient as seen by the transport layer -- and as snapshotted onto
 * report_dispatch.recipients_json. Deliberately a plain copy of the fields
 * ReportRecipient had at dispatch time, not a foreign key: the dispatch
 * record must stay immutable even if the recipient roster changes later. */
public record DispatchRecipient(String recipientId, String name, String email, String role) {
}
