package com.moveinsync.pulse.report;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

public interface ReportDispatchRepository extends JpaRepository<ReportDispatch, String> {

    /** Idempotency check: an identical (tenant, period, content) dispatch
     * already recorded within the window ReportDispatchService passes in --
     * see its class docstring on the one-hour rule. Scoped to `status` (the
     * service always passes "SUCCESS") so a previous FAILED attempt never
     * blocks a retry of the same content -- nothing was actually sent, so
     * there is nothing to be a duplicate of. */
    Optional<ReportDispatch> findFirstByTenantIdAndPeriodAndContentHashAndStatusAndDispatchedAtAfterOrderByDispatchedAtDesc(
            String tenantId, String period, String contentHash, String status, Instant after);

    List<ReportDispatch> findByTenantIdOrderByDispatchedAtDesc(String tenantId);

    List<ReportDispatch> findByTenantIdAndPeriodOrderByDispatchedAtDesc(String tenantId, String period);
}
