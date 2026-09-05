package com.moveinsync.pulse.insight;

import java.util.List;

import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.tenant.MissingTenantException;
import com.moveinsync.pulse.tenant.TenantContextHolder;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * The brief cache is the obvious place for a tenant leak to reappear after all the work at
 * the data layer to prevent one -- one shared entry and every tenant sees the first caller's
 * feed. These tests exist for that, not for the caching.
 */
@SpringBootTest(properties = "pulse.brief.cache-ttl=30s")
@Transactional
class BriefCacheTest {

    private static final String CATALYST = "catalyst";
    private static final String VANTA = "vanta";

    @Autowired
    private BriefCache briefCache;

    @Autowired
    private JdbcTemplate jdbc;

    @BeforeEach
    void insertRowsForBothTenants() {
        briefCache.invalidateAll();
        TenantContextHolder.clear();
        insertInsight(CATALYST, "cache_catalyst_1", 90);
        insertInsight(CATALYST, "cache_catalyst_2", 80);
        insertInsight(VANTA, "cache_vanta_1", 70);
    }

    @Test
    @DisplayName("a warm cache for one tenant is never served to another")
    void cacheIsKeyedPerTenant() {
        TenantContextHolder.set(CATALYST);
        List<InsightPacket> catalystFeed = briefCache.insights();
        assertThat(catalystFeed).extracting(InsightPacket::insightId)
                .contains("cache_catalyst_1", "cache_catalyst_2")
                .doesNotContain("cache_vanta_1");

        // catalyst's entry is now warm. vanta must still get its own feed.
        TenantContextHolder.set(VANTA);
        List<InsightPacket> vantaFeed = briefCache.insights();
        assertThat(vantaFeed).extracting(InsightPacket::insightId)
                .contains("cache_vanta_1")
                .doesNotContain("cache_catalyst_1", "cache_catalyst_2");
    }

    @Test
    @DisplayName("a second read within the TTL is served from the cache")
    void secondReadIsACacheHit() {
        TenantContextHolder.set(CATALYST);
        List<InsightPacket> first = briefCache.insights();
        List<InsightPacket> second = briefCache.insights();

        assertThat(second).isSameAs(first);
    }

    @Test
    @DisplayName("invalidate forces the next read back to the database")
    void invalidateDropsTheEntry() {
        TenantContextHolder.set(CATALYST);
        List<InsightPacket> first = briefCache.insights();

        briefCache.invalidate(CATALYST);
        List<InsightPacket> afterInvalidate = briefCache.insights();

        assertThat(afterInvalidate).isNotSameAs(first);
        assertThat(afterInvalidate).extracting(InsightPacket::insightId)
                .containsExactlyInAnyOrderElementsOf(first.stream().map(InsightPacket::insightId).toList());
    }

    @Test
    @DisplayName("no tenant in context throws instead of caching under a null key")
    void missingTenantThrows() {
        TenantContextHolder.clear();

        assertThatThrownBy(() -> briefCache.insights()).isInstanceOf(MissingTenantException.class);
    }

    private void insertInsight(String tenantId, String insightId, int severity) {
        jdbc.update("""
                insert into insight (
                    tenant_id, insight_id, severity,
                    metric_id, metric_name, metric_value, metric_unit, metric_n, metric_window,
                    entity_dim, entity_ref, entity_name,
                    data_quality_excluded_pct, data_quality_confidence,
                    narrative_headline, narrative_body)
                values (?, ?, ?, 'cache_metric', 'Cache metric', 1.0, '%', 1, 'trailing_30d',
                        'fleet', 'ALL', 'Fleet-wide', 0.0, 'high', ?, 'cache fixture')
                """, tenantId, insightId, severity, "headline " + insightId);
    }
}
