package com.moveinsync.pulse.config;

import java.util.concurrent.atomic.AtomicReference;

import org.springframework.stereotype.Component;

/**
 * Whether the platform database answered during startup.
 *
 * <p>Recorded by {@link FlywayConfig}, which is the first thing to touch Neon, and read by
 * {@link SchemaValidationConfig} a moment later. Sharing that one fact means the application
 * does not spend a second connection timeout rediscovering that the database is still asleep.
 */
@Component
public class PlatformDbBootState {

    private final AtomicReference<String> unreachableReason = new AtomicReference<>();

    public void markUnreachable(String reason) {
        unreachableReason.set(reason);
    }

    public boolean reachedAtStartup() {
        return unreachableReason.get() == null;
    }

    public String unreachableReason() {
        return unreachableReason.get();
    }
}
