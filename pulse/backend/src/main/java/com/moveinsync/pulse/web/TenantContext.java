package com.moveinsync.pulse.web;

import org.springframework.stereotype.Component;
import org.springframework.web.context.annotation.RequestScope;

/** The tenant resolved from X-Tenant-Id for the current request. Populated by
 * {@link TenantFilter} before any controller runs. */
@Component
@RequestScope
public class TenantContext {

    private String tenantId;

    public String tenantId() {
        return tenantId;
    }

    void setTenantId(String tenantId) {
        this.tenantId = tenantId;
    }
}
