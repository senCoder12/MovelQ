package com.moveinsync.pulse.config;

import javax.sql.DataSource;

import org.springframework.beans.BeansException;
import org.springframework.beans.factory.config.BeanPostProcessor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;

/** Wraps the application DataSource in {@link SlowQueryLoggingDataSource}.
 *
 * <p>A BeanPostProcessor rather than a replacement @Bean so Spring Boot still builds and
 * configures the Hikari pool from spring.datasource.*; this only decorates the result. */
@Configuration
public class SlowQueryLoggingConfig {

    @Bean
    static BeanPostProcessor slowQueryDataSourceDecorator(Environment environment) {
        return new SlowQueryDataSourceDecorator(
                environment.getProperty("pulse.latency.slow-query-ms", Long.class, 500L));
    }

    /** Named rather than anonymous: BeanPostProcessors are instantiated before most of the
     * context exists, and a top-level class keeps that early wiring obvious. */
    static final class SlowQueryDataSourceDecorator implements BeanPostProcessor {

        private final long thresholdMs;

        SlowQueryDataSourceDecorator(long thresholdMs) {
            this.thresholdMs = thresholdMs;
        }

        @Override
        public Object postProcessAfterInitialization(Object bean, String beanName) throws BeansException {
            if (bean instanceof DataSource dataSource && !(bean instanceof SlowQueryLoggingDataSource)) {
                return new SlowQueryLoggingDataSource(dataSource, thresholdMs);
            }
            return bean;
        }
    }
}
