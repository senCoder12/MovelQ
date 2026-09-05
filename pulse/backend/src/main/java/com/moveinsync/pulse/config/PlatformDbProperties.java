package com.moveinsync.pulse.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** Latency thresholds. Neon runs in us-east-2 and the demo runs from India, so a healthy
 * round trip is already 150-250ms; these are the points past which something is wrong
 * rather than merely far away. */
@ConfigurationProperties(prefix = "pulse.latency")
public record PlatformDbProperties(Long slowQueryMs, Long slowRequestMs) {

    public PlatformDbProperties {
        slowQueryMs = slowQueryMs == null ? 500L : slowQueryMs;
        slowRequestMs = slowRequestMs == null ? 800L : slowRequestMs;
    }
}
