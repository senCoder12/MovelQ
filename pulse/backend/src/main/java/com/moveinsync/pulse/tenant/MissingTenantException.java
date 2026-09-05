package com.moveinsync.pulse.tenant;

/** Thrown when data access is attempted with no tenant in {@link TenantContextHolder}.
 *
 * <p>This is deliberately fatal rather than a fallback to "return everything". A repository
 * call with no tenant is a bug in the caller, and the failure mode of guessing is that one
 * customer sees another customer's fleet.
 */
public class MissingTenantException extends IllegalStateException {

    public MissingTenantException(String operation) {
        super("no tenant in context for " + operation
                + " -- data access is tenant-scoped; set TenantContextHolder or send X-Tenant-Id");
    }
}
