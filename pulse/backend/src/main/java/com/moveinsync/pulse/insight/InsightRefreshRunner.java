package com.moveinsync.pulse.insight;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import com.moveinsync.pulse.tenant.TenantContextHolder;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

/**
 * Runs detection for every tenant at startup when given {@code --refresh-insights}.
 *
 * <p>Separate from a schedule on purpose. Detection scans the warehouse, and the warehouse
 * only changes when ingest runs, so refreshing on a timer would mostly burn a Neon round
 * trip per tenant to rewrite identical rows. Refresh after ingest, or from
 * {@code POST /api/insights/refresh}.
 */
@Component
public class InsightRefreshRunner implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(InsightRefreshRunner.class);
    private static final String FLAG = "--refresh-insights";

    private final InsightSyncService sync;

    public InsightRefreshRunner(InsightSyncService sync) {
        this.sync = sync;
    }

    @Override
    public void run(String... args) {
        if (Arrays.stream(args).noneMatch(FLAG::equals)) {
            return;
        }
        // The loop lives here rather than in the service so each sync() call crosses a bean
        // boundary and actually gets its transaction. Tenants are independent, so one
        // failing does not stop the others.
        List<InsightSyncService.SyncResult> results = new ArrayList<>();
        for (String tenantId : sync.tenants()) {
            try {
                results.add(TenantContextHolder.runAs(tenantId, () -> sync.sync(tenantId)));
            } catch (RuntimeException ex) {
                log.warn("insight sync failed for tenant {}: {}", tenantId, ex.toString());
            }
        }
        int written = results.stream().mapToInt(InsightSyncService.SyncResult::written).sum();
        int retired = results.stream().mapToInt(InsightSyncService.SyncResult::retired).sum();
        log.info("insight refresh complete: {} tenant(s), {} insight(s) written, {} retired",
                results.size(), written, retired);
    }
}
