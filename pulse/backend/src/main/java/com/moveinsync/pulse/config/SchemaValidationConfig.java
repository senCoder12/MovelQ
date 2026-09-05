package com.moveinsync.pulse.config;

import org.hibernate.cfg.AvailableSettings;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.orm.jpa.HibernatePropertiesCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Keeps a sleeping Neon branch from turning into a failed boot.
 *
 * <p>{@code spring.jpa.hibernate.ddl-auto} is {@code validate}: Flyway owns the schema and
 * Hibernate's job is to confirm the mapping still matches it. That check needs a live
 * connection, and it runs while the EntityManagerFactory is being built -- so with Neon
 * suspended it would take the application down before it could serve anything, /api/health
 * included.
 *
 * <p>Deferring the EntityManagerFactory itself does not work: it is {@code LoadTimeWeaverAware},
 * and Spring initialises those beans eagerly regardless of lazy-init. So the narrower thing is
 * done instead -- when the database did not answer during startup, this boot skips schema
 * validation and says so. Nothing is silently relaxed: the warning names the reason,
 * /api/health reports the platform database as unreachable, and the next start with a
 * reachable database validates normally.
 */
@Configuration
public class SchemaValidationConfig {

    private static final Logger log = LoggerFactory.getLogger(SchemaValidationConfig.class);

    @Bean
    HibernatePropertiesCustomizer skipSchemaValidationWhenDatabaseIsAsleep(PlatformDbBootState bootState) {
        return properties -> {
            if (bootState.reachedAtStartup()) {
                return;
            }
            log.warn("platform database did not answer during startup ({}). "
                    + "Skipping Hibernate schema validation for this boot so the API still comes up; "
                    + "/api/health will report the platform database as unreachable.",
                    bootState.unreachableReason());
            properties.put(AvailableSettings.HBM2DDL_AUTO, "none");
        };
    }
}
