package com.moveinsync.pulse.web;

import com.moveinsync.pulse.tenant.TenantContextHolder;

import org.springframework.stereotype.Component;

/** The tenant the current call is acting as.
 *
 * <p>A thin, injectable view over {@link TenantContextHolder}. It used to hold the tenant
 * itself in a request-scoped bean; the state moved to a ThreadLocal so the same tenant is
 * visible to the repository-layer filter aspect and to callers with no HTTP request
 * (the seed runner, jobs, tests). Populated by {@link TenantFilter} for every /api/** call.
 */
@Component
public class TenantContext {

    /** The current tenant, or null when there isn't one. */
    public String tenantId() {
        return TenantContextHolder.get();
    }

    /** The current tenant, or {@link com.moveinsync.pulse.tenant.MissingTenantException}. */
    public String requireTenantId() {
        return TenantContextHolder.require("request");
    }

    public void setTenantId(String tenantId) {
        TenantContextHolder.set(tenantId);
    }

    public void clear() {
        TenantContextHolder.clear();
    }
}
