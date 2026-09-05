package com.moveinsync.pulse.web;

import java.util.List;

import com.moveinsync.pulse.agent.dto.InsightPacket;

import org.springframework.stereotype.Component;

/** Filters agent-supplied insight packets by tenant. An insight is tenant-scoped when its
 * entity.dim is "tenant"; everything else (fleet-wide, vendor, segment, ...) is not
 * tenant-specific and passes through regardless of the caller's tenant. No tenant header
 * means no filtering.
 *
 * <p>Insights read from our own database are scoped at the repository by
 * {@link com.moveinsync.pulse.tenant.TenantFilterAspect}, which is why the controllers no
 * longer use this. It survives for {@link com.moveinsync.pulse.action.ActionDraftService},
 * which drafts against a packet fetched from the agent rather than from the database --
 * that path never passes through the repository filter, so this is the only thing standing
 * between a caller and drafting an action on another tenant's insight. */
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
