package com.moveinsync.pulse.config;

import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.MigrationInfo;
import org.flywaydb.core.api.output.MigrateResult;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.flyway.FlywayMigrationStrategy;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Runs the migrations at startup, reports the version, and refuses to take the application
 * down with it.
 *
 * <p>A failed migration here is almost always Neon being asleep or the network being slow,
 * not a broken migration -- and an API that boots and reports itself degraded is more useful
 * during a demo than one that will not start. A genuinely broken migration still shows up
 * immediately: as a WARN at boot, as a degraded /api/health, and as a Hibernate validation
 * failure on the first query.
 *
 * <p>Migrations are still applied exactly once; Flyway's schema history does that, not this.
 * A failure here is also recorded in {@link PlatformDbBootState}, which is what tells
 * {@link SchemaValidationConfig} to skip schema validation for this boot.
 */
@Configuration
public class FlywayConfig {

    private static final Logger log = LoggerFactory.getLogger(FlywayConfig.class);

    @Bean
    FlywayMigrationStrategy resilientMigrationStrategy(PlatformDbBootState bootState) {
        return flyway -> {
            try {
                MigrateResult result = flyway.migrate();
                log.info("Flyway: schema at version {} ({} migration(s) applied this run, target database {})",
                        currentVersion(flyway), result.migrationsExecuted, result.database);
            } catch (RuntimeException ex) {
                // Flyway is the first thing to touch Neon, so its failure is also the cheapest
                // signal that the database is unreachable. SchemaValidationConfig reads this
                // rather than paying another connection timeout to learn the same thing.
                bootState.markUnreachable(ex.toString());
                log.warn("Flyway migration did not complete: {}. "
                        + "Starting anyway -- /api/health will report the platform database as degraded. "
                        + "If Neon was suspended this usually resolves on the next start.", ex.toString());
            }
        };
    }

    /** The version actually applied, read back from the schema history. */
    private static String currentVersion(Flyway flyway) {
        try {
            MigrationInfo current = flyway.info().current();
            return current == null ? "<empty schema>" : current.getVersion() + " - " + current.getDescription();
        } catch (RuntimeException ex) {
            return "<unknown>";
        }
    }
}
