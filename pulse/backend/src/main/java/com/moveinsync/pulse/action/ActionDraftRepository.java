package com.moveinsync.pulse.action;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

public interface ActionDraftRepository extends JpaRepository<ActionDraft, String> {

    List<ActionDraft> findByTenantIdAndInsightIdOrderByCreatedAtDesc(String tenantId, String insightId);

    List<ActionDraft> findByTenantIdOrderByCreatedAtDesc(String tenantId);

    List<ActionDraft> findByTenantIdAndStatusOrderByCreatedAtDesc(String tenantId, ActionStatus status);

    Optional<ActionDraft> findByActionIdAndTenantId(String actionId, String tenantId);
}
