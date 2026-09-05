package com.moveinsync.pulse.report.dispatch;

import java.time.Instant;

/** What a transport hands back. `providerMessageId` is whatever the
 * underlying transport's own audit trail uses to identify the send (a JavaMail
 * Message-Id for SMTP); LoggedTransport has no such concept and always
 * returns null there. `error` is populated only on FAILED. */
public record DispatchResult(
        DispatchStatus status,
        String transport,
        Instant dispatchedAt,
        String providerMessageId,
        String error) {
}
