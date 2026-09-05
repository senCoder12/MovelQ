package com.moveinsync.pulse.report.dispatch;

import java.time.Instant;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/** The default transport: writes the dispatch to the application log and
 * returns SUCCESS. This is deliberately not a no-op -- report_dispatch is
 * the durable record regardless of transport, so "logged" just means the
 * report_dispatch row IS the delivery, there is no second copy anywhere
 * else. Active whenever pulse.dispatch.transport is "logged" or unset. */
@Component
@ConditionalOnProperty(prefix = "pulse.dispatch", name = "transport", havingValue = "logged", matchIfMissing = true)
public class LoggedTransport implements ReportTransport {

    private static final Logger log = LoggerFactory.getLogger(LoggedTransport.class);

    @Override
    public DispatchResult send(DispatchRequest request) {
        log.info(
                "LOGGED dispatch: tenant={} reportId={} recipients={} subject=\"{}\" bytes(html={}, text={})",
                request.tenant(), request.reportId(), request.recipients().stream().map(DispatchRecipient::email).toList(),
                request.subject(), request.bodyHtml().length(), request.bodyText().length());
        return new DispatchResult(DispatchStatus.SUCCESS, name(), Instant.now(), null, null);
    }

    @Override
    public String name() {
        return "logged";
    }
}
