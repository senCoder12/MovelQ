package com.moveinsync.pulse.config;

import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** Brief feed caching. A zero or negative TTL disables the cache entirely, which is what
 * the tests run with -- they assert on query counts and a cache would hide them. */
@ConfigurationProperties(prefix = "pulse.brief")
public record BriefCacheProperties(Duration cacheTtl) {

    public BriefCacheProperties {
        cacheTtl = cacheTtl == null ? Duration.ofSeconds(30) : cacheTtl;
    }

    public boolean cacheEnabled() {
        return !cacheTtl.isZero() && !cacheTtl.isNegative();
    }
}
