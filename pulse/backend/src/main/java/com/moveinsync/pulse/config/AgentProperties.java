package com.moveinsync.pulse.config;

import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** Connection settings for the Python agent service. */
@ConfigurationProperties(prefix = "pulse.agent")
public record AgentProperties(String baseUrl, Duration connectTimeout, Duration readTimeout) {

    public AgentProperties {
        connectTimeout = connectTimeout == null ? Duration.ofSeconds(2) : connectTimeout;
        readTimeout = readTimeout == null ? Duration.ofSeconds(5) : readTimeout;
    }
}
