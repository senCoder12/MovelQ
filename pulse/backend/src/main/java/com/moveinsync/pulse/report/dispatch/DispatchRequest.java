package com.moveinsync.pulse.report.dispatch;

import java.util.List;

/** Everything a transport needs to send one report, and nothing it doesn't --
 * a transport never sees a LeadershipPack or an insight, only an already
 * rendered subject/body pair. `attachments` is always empty today (no
 * attachment support has landed); it is on the contract now so adding one
 * later does not change every transport's method signature. */
public record DispatchRequest(
        String tenant,
        String reportId,
        List<DispatchRecipient> recipients,
        String subject,
        String bodyHtml,
        String bodyText,
        List<String> attachments,
        String sender) {
}
