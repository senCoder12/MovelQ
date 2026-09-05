package com.moveinsync.pulse.alert;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

public interface AlertRepository extends JpaRepository<Alert, String> {

    List<Alert> findByTenantIdOrderByFiredAtDesc(String tenantId);

    Optional<Alert> findByAlertIdAndTenantId(String alertId, String tenantId);

    /** Cooldown check: the most recent fire of this (tenant, rule, entity),
     * regardless of status -- an acknowledged or muted alert still counts
     * toward cooldown, only a mute's own suppressed_until (a separate
     * table) blocks longer than that. */
    Optional<Alert> findFirstByTenantIdAndRuleIdAndEntityDimAndEntityValueOrderByFiredAtDesc(
            String tenantId, String ruleId, String entityDim, String entityValue);

    /** Repeat-pass candidates: still NEW, immediate, older than the repeat
     * threshold, and not itself already a repeat (repeat_of is null) --
     * whether it has ALREADY been repeated is checked separately via
     * existsByRepeatOf, since "once only" means checking the far side of
     * that relationship too. */
    List<Alert> findByTenantIdAndStatusAndUrgencyAndFiredAtBeforeAndRepeatOfIsNull(
            String tenantId, AlertStatus status, String urgency, Instant before);

    boolean existsByRepeatOf(String alertId);

    long countByTenantIdAndStatus(String tenantId, AlertStatus status);
}
