package com.moveinsync.pulse.report.dispatch;

import java.time.Instant;
import java.util.List;
import java.util.Locale;

import com.moveinsync.pulse.config.SmtpProperties;

import jakarta.mail.internet.MimeMessage;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.mail.MailException;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.stereotype.Component;

/** Real email, via the JavaMailSender Spring Boot autoconfigures from
 * spring.mail.* (itself sourced from PULSE_SMTP_HOST/PORT/USER/PASSWORD --
 * see application.yml). One attempt, no retry: a failed send is recorded as
 * FAILED with the underlying error rather than silently tried again, so a
 * transient SMTP hiccup never turns into a duplicate delivery. The 10s
 * connect/read/write timeout lives in spring.mail.properties in
 * application.yml, not here -- JavaMailSenderImpl reads it from there.
 *
 * The allowlist guard is the actual safety net: this runs before any
 * network call, so a misconfigured recipient roster fails closed instead of
 * mailing an unexpected domain. */
@Component
@ConditionalOnProperty(prefix = "pulse.dispatch", name = "transport", havingValue = "smtp")
public class SmtpTransport implements ReportTransport {

    private static final Logger log = LoggerFactory.getLogger(SmtpTransport.class);

    private final JavaMailSender mailSender;
    private final SmtpProperties smtpProperties;

    public SmtpTransport(JavaMailSender mailSender, SmtpProperties smtpProperties) {
        this.mailSender = mailSender;
        this.smtpProperties = smtpProperties;
    }

    @Override
    public DispatchResult send(DispatchRequest request) {
        List<String> disallowed = request.recipients().stream()
                .map(DispatchRecipient::email)
                .filter(email -> !isAllowed(email))
                .toList();
        if (!disallowed.isEmpty()) {
            String error = "recipient domain not on pulse.smtp.allowlist-domains: " + disallowed;
            log.warn("SMTP dispatch refused: {}", error);
            return new DispatchResult(DispatchStatus.FAILED, name(), Instant.now(), null, error);
        }

        try {
            MimeMessage message = mailSender.createMimeMessage();
            MimeMessageHelper helper = new MimeMessageHelper(message, true, "UTF-8");
            helper.setFrom(request.sender());
            helper.setTo(request.recipients().stream().map(DispatchRecipient::email).toArray(String[]::new));
            helper.setSubject(request.subject());
            helper.setText(request.bodyText(), request.bodyHtml());

            mailSender.send(message);
            return new DispatchResult(DispatchStatus.SUCCESS, name(), Instant.now(), message.getMessageID(), null);
        } catch (MailException | jakarta.mail.MessagingException ex) {
            log.warn("SMTP dispatch failed: {}", ex.getMessage());
            return new DispatchResult(DispatchStatus.FAILED, name(), Instant.now(), null, ex.getMessage());
        }
    }

    @Override
    public String name() {
        return "smtp";
    }

    /** Matches the domain itself or any subdomain of it (transport.head@
     * catalyst.example.com is allowed by an "example.com" entry) -- the
     * safety property this guards is "within the reserved example.com zone,
     * never a real mailbox" (RFC 2606), and a subdomain of example.com is
     * exactly as safe as example.com itself. */
    private boolean isAllowed(String email) {
        int at = email.lastIndexOf('@');
        if (at < 0) {
            return false;
        }
        String domain = email.substring(at + 1).toLowerCase(Locale.ROOT);
        return smtpProperties.allowlistDomains().stream()
                .map(allowed -> allowed.toLowerCase(Locale.ROOT))
                .anyMatch(allowed -> domain.equals(allowed) || domain.endsWith("." + allowed));
    }
}
