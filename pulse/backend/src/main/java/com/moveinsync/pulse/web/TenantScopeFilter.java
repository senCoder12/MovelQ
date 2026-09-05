package com.moveinsync.pulse.web;

import java.util.List;

import com.moveinsync.pulse.agent.dto.InsightPacket;

import org.springframework.stereotype.Component;

/** Filters insights by tenant. An insight is tenant-scoped when its entity.dim is
 * "tenant"; everything else (fleet-wide, vendor, segment, ...) is not tenant-specific
 * and passes through regardless of the caller's tenant. No tenant header means no
 * filtering. This is a seam, not detection logic -- today's mock data has no
 * tenant-scoped insights, so it is a no-op until real tenant-scoped data lands. */
@Component
public class TenantScopeFilter {

    public List<InsightPacket> apply(List<InsightPacket> insights, String tenantId) {
        if (tenantId == null || tenantId.isBlank()) {
            return insights;
        }
        return insights.stream().filter(insight -> matchesTenant(insight, tenantId)).toList();
    }

    public boolean matchesTenant(InsightPacket insight, String tenantId) {
        if (tenantId == null || tenantId.isBlank()) {
            return true;
        }
        if (!"tenant".equals(insight.entity().dim())) {
            return true;
        }
        return tenantId.equals(insight.entity().id());
    }
}
