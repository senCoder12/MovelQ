package com.moveinsync.pulse.insight;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

import jakarta.annotation.PreDestroy;

import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.config.BriefCacheProperties;
import com.moveinsync.pulse.tenant.TenantContextHolder;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Short-lived per-tenant cache in front of the brief feed.
 *
 * <p>The brief is the first thing the demo loads and the thing a tenant switch re-loads.
 * Even at one query it costs a full round trip to us-east-2, which from India is ~300ms
 * before anything else happens. Insights are recomputed by the agent on a far slower cycle
 * than anyone clicks, so serving a few-second-old feed costs nothing real.
 *
 * <p>The cache is keyed on the tenant from {@link TenantContextHolder}, and the key is
 * required rather than defaulted -- a cache with a null or shared key is a cross-tenant leak
 * with extra steps, which is why {@link #insights()} resolves the tenant itself instead of
 * trusting a caller to pass the right one.
 *
 * <p>An expired entry is served anyway and refreshed on a background thread, rather than
 * making the unlucky caller wait. That is not premature cleverness: a plain expire-and-fetch
 * cache measured 850ms-1s on every miss here, because a round trip to Neon costs ~300ms when
 * the connection is busy and 550-800ms after a quiet gap -- and the caller who pays it is
 * whoever clicks first after the demo has been sitting idle. Serving data a few seconds past
 * its TTL is worth more than that. Entries older than {@link #STALE_LIMIT_MULTIPLIER} times
 * the TTL are refetched synchronously, so a persistently failing refresh cannot serve
 * something ancient forever.
 */
@Component
public class BriefCache {

    private static final Logger log = LoggerFactory.getLogger(BriefCache.class);

    /** How far past its TTL an entry may be served while a refresh is in flight. */
    private static final int STALE_LIMIT_MULTIPLIER = 10;

    private final InsightQueryService insights;
    private final BriefCacheProperties properties;
    private final Map<String, Entry> byTenant = new ConcurrentHashMap<>();

    /** One thread, and a queue that drops duplicates via the per-entry refreshing flag.
     * Refreshing the brief is never urgent enough to justify more. */
    private final ThreadPoolExecutor refreshExecutor = new ThreadPoolExecutor(
            0, 1, 60L, TimeUnit.SECONDS, new LinkedBlockingQueue<>(16),
            runnable -> {
                Thread thread = new Thread(runnable, "brief-cache-refresh");
                thread.setDaemon(true);
                return thread;
            },
            new ThreadPoolExecutor.DiscardPolicy());

    public BriefCache(InsightQueryService insights, BriefCacheProperties properties) {
        this.insights = insights;
        this.properties = properties;
    }

    @PreDestroy
    void shutdown() {
        refreshExecutor.shutdownNow();
    }

    /** The brief feed for the tenant in context, cached for the configured TTL. */
    public List<InsightPacket> insights() {
        String tenantId = TenantContextHolder.require("brief");
        if (!properties.cacheEnabled()) {
            return insights.listInsights();
        }
        long now = System.nanoTime();
        Entry cached = byTenant.get(tenantId);
        if (cached != null && cached.isFreshAt(now)) {
            return cached.packets();
        }
        if (cached != null && !cached.isTooStaleAt(now, properties.cacheTtl().toNanos())) {
            // Expired but usable: hand it over now, fetch the replacement behind the caller.
            refreshInBackground(tenantId, cached);
            return cached.packets();
        }
        // Nothing cached, or too old to stand behind. This caller pays the round trip.
        return fetchAndStore(tenantId);
    }

    private List<InsightPacket> fetchAndStore(String tenantId) {
        List<InsightPacket> packets = insights.listInsights();
        byTenant.put(tenantId, new Entry(packets, System.nanoTime() + properties.cacheTtl().toNanos(),
                new AtomicBoolean(false)));
        log.debug("brief cache fill for tenant {} -- {} insight(s), good for {}",
                tenantId, packets.size(), properties.cacheTtl());
        return packets;
    }

    /** At most one refresh per tenant in flight; the rest keep reading the stale entry. */
    private void refreshInBackground(String tenantId, Entry stale) {
        if (!stale.refreshing().compareAndSet(false, true)) {
            return;
        }
        refreshExecutor.execute(() -> {
            try {
                TenantContextHolder.runAs(tenantId, () -> fetchAndStore(tenantId));
            } catch (RuntimeException ex) {
                // Keep serving the stale entry and try again on the next read. A failed
                // refresh must not turn into a failed request.
                stale.refreshing().set(false);
                log.warn("brief cache refresh failed for tenant {}: {}", tenantId, ex.toString());
            }
        });
    }

    /** Drops the cached feed for one tenant. For use after anything that rewrites insights. */
    public void invalidate(String tenantId) {
        byTenant.remove(tenantId);
    }

    public void invalidateAll() {
        byTenant.clear();
    }

    private record Entry(List<InsightPacket> packets, long expiresAtNanos, AtomicBoolean refreshing) {

        boolean isFreshAt(long nowNanos) {
            return nowNanos - expiresAtNanos < 0;
        }

        boolean isTooStaleAt(long nowNanos, long ttlNanos) {
            return nowNanos - (expiresAtNanos + ttlNanos * (STALE_LIMIT_MULTIPLIER - 1)) >= 0;
        }
    }
}
