package com.moveinsync.pulse.config;

import java.util.List;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** pulse.smtp.allowlist-domains -- the only domains SmtpTransport will ever
 * address mail to. Defaults to example.com alone: a checkout that flips
 * pulse.dispatch.transport to "smtp" without also widening this list still
 * cannot reach a real inbox, which is the point of it (seed recipients are
 * all on example.com for exactly this reason). */
@ConfigurationProperties(prefix = "pulse.smtp")
public record SmtpProperties(List<String> allowlistDomains) {

    public SmtpProperties {
        allowlistDomains = (allowlistDomains == null || allowlistDomains.isEmpty())
                ? List.of("example.com")
                : allowlistDomains;
    }
}
