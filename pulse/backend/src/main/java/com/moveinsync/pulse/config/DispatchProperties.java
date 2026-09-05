package com.moveinsync.pulse.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** pulse.dispatch.* -- which ReportTransport is active and the address a
 * report claims to be from. `transport` defaults to "logged": a fresh
 * checkout never sends real email until someone deliberately opts in. */
@ConfigurationProperties(prefix = "pulse.dispatch")
public record DispatchProperties(String transport, String fromAddress) {

    public DispatchProperties {
        transport = (transport == null || transport.isBlank()) ? "logged" : transport;
        fromAddress = (fromAddress == null || fromAddress.isBlank()) ? "pulse-reports@example.com" : fromAddress;
    }
}
