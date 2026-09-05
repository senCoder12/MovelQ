package com.moveinsync.pulse.action;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

/** Action drafts. Tenant-scoped like everything else; see {@link com.moveinsync.pulse.insight.InsightRepository}
 * for why findById is overridden. */
public interface ActionDraftRepository extends JpaRepository<ActionDraft, Long> {

    @Override
    @Query("select a from ActionDraft a where a.id = :id")
    Optional<ActionDraft> findById(@Param("id") Long id);

    @Query("select a from ActionDraft a where a.actionId = :actionId")
    Optional<ActionDraft> findByActionId(@Param("actionId") String actionId);

    @Query("select a from ActionDraft a where a.insight.insightId = :insightId order by a.createdAt asc")
    List<ActionDraft> findByInsightId(@Param("insightId") String insightId);

    boolean existsByActionId(String actionId);
}
