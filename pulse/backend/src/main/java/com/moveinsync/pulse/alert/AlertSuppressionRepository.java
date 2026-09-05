package com.moveinsync.pulse.alert;

import java.time.Instant;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

public interface AlertSuppressionRepository extends JpaRepository<AlertSuppression, String> {

    /** Any row for this (tenant, rule, entity) still active right now --
     * existence is enough, AlertScanService doesn't need which row. */
    Optional<AlertSuppression> findFirstByTenantIdAndRuleIdAndEntityDimAndEntityValueAndSuppressedUntilAfterOrderBySuppressedUntilDesc(
            String tenantId, String ruleId, String entityDim, String entityValue, Instant now);
}
