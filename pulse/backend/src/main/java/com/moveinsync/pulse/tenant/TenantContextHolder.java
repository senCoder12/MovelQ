package com.moveinsync.pulse.tenant;

import java.util.function.Supplier;

/** The tenant the current thread is acting as.
 *
 * <p>A {@code ThreadLocal} rather than a request-scoped bean because the tenant has to be
 * readable from places that have no HTTP request: the seed runner, scheduled jobs, and the
 * {@link TenantFilterAspect} that sits underneath every repository call.
 *
 * <p>{@link com.moveinsync.pulse.web.TenantFilter} sets it per request and always clears it,
 * so a pooled request thread never inherits the previous request's tenant.
 */
public final class TenantContextHolder {

    private static final ThreadLocal<String> CURRENT = new ThreadLocal<>();

    private TenantContextHolder() {
    }

    public static String get() {
        return CURRENT.get();
    }

    /** The tenant, or {@link MissingTenantException} if there isn't one. */
    public static String require(String operation) {
        String tenantId = CURRENT.get();
        if (tenantId == null || tenantId.isBlank()) {
            throw new MissingTenantException(operation);
        }
        return tenantId;
    }

    public static void set(String tenantId) {
        CURRENT.set(tenantId);
    }

    public static void clear() {
        CURRENT.remove();
    }

    /** Runs {@code body} as {@code tenantId}, restoring whatever was there before. Used by
     * the seed runner, which writes for several tenants in one pass. */
    public static <T> T runAs(String tenantId, Supplier<T> body) {
        String previous = CURRENT.get();
        CURRENT.set(tenantId);
        try {
            return body.get();
        } finally {
            if (previous == null) {
                CURRENT.remove();
            } else {
                CURRENT.set(previous);
            }
        }
    }

    public static void runAs(String tenantId, Runnable body) {
        runAs(tenantId, () -> {
            body.run();
            return null;
        });
    }
}
