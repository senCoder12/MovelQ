package com.moveinsync.pulse.observability;

import com.moveinsync.pulse.config.PlatformDbProperties;
import com.moveinsync.pulse.tenant.TenantContextHolder;

import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Times every controller method end to end.
 *
 * <p>Each line carries the tenant, because the two tenants have different amounts of data and
 * "the brief is slow" is a different problem for each. Anything past the slow-request
 * threshold is a WARN: at that point the round trip to us-east-2 is no longer the explanation
 * and the endpoint needs a cache or a narrower query.
 */
@Aspect
@Component
public class ControllerTimingAspect {

    private static final Logger log = LoggerFactory.getLogger(ControllerTimingAspect.class);

    private final long slowRequestMs;

    public ControllerTimingAspect(PlatformDbProperties properties) {
        this.slowRequestMs = properties.slowRequestMs();
    }

    @Around("within(@org.springframework.web.bind.annotation.RestController *)")
    public Object time(ProceedingJoinPoint joinPoint) throws Throwable {
        long startedAt = System.nanoTime();
        String method = joinPoint.getSignature().toShortString();
        boolean failed = false;
        try {
            return joinPoint.proceed();
        } catch (Throwable ex) {
            failed = true;
            throw ex;
        } finally {
            long elapsedMs = (System.nanoTime() - startedAt) / 1_000_000;
            String tenantId = TenantContextHolder.get();
            if (elapsedMs > slowRequestMs) {
                log.warn("{} took {}ms (tenant={}, threshold {}ms){}",
                        method, elapsedMs, tenantId, slowRequestMs, failed ? " [failed]" : "");
            } else {
                log.info("{} {}ms (tenant={}){}", method, elapsedMs, tenantId, failed ? " [failed]" : "");
            }
        }
    }
}
