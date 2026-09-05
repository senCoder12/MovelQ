package com.moveinsync.pulse.job;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/** Runs one scan per known tenant when the app boots, so alerts already
 * exist without anyone opening the app or clicking anything -- exactly the
 * "no human involvement" the alerting feature is meant to demonstrate.
 * This is a one-shot ApplicationRunner, not a scheduler: it fires once at
 * startup and never again on its own. Deliberately not @Scheduled -- see
 * ScanService's class docstring on why this stays minimal.
 *
 * The tenant list is the same fixed four TenantService.TENANTS uses on the
 * frontend (and V3__report_recipient.sql seeded); there is no tenant table
 * to read this from instead.
 *
 * Off by default in tests (pulse.jobs.startup-scan-enabled=false in
 * src/test/resources/application.yml) -- a unit test's Spring context has
 * no live agent to call, and this is the only thing in the app that would
 * otherwise make a real HTTP call the moment any test boots the context. */
@Component
@ConditionalOnProperty(prefix = "pulse.jobs", name = "startup-scan-enabled", matchIfMissing = true)
public class ScanStartupRunner implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(ScanStartupRunner.class);
    private static final String[] TENANTS = { "catalyst", "orbit", "pinnacle", "vanta" };

    private final ScanService scanService;

    public ScanStartupRunner(ScanService scanService) {
        this.scanService = scanService;
    }

    @Override
    public void run(ApplicationArguments args) {
        for (String tenantId : TENANTS) {
            try {
                ScanRunView result = scanService.runForTenant(tenantId);
                log.info("Startup scan for tenant {}: status={} fired={} suppressed={} repeated={}", tenantId,
                        result.status(), result.alertsFired(), result.alertsSuppressed(), result.alertsRepeated());
            } catch (RuntimeException ex) {
                // One tenant's agent hiccup should not stop the others from scanning,
                // or stop the application from starting at all.
                log.warn("Startup scan failed for tenant {}: {}", tenantId, ex.getMessage());
            }
        }
    }
}
