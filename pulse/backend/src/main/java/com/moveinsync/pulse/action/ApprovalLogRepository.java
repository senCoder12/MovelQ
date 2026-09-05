package com.moveinsync.pulse.action;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

/** The approval trail for action drafts. Append-only. */
public interface ApprovalLogRepository extends JpaRepository<ApprovalLog, Long> {

    @Query("select l from ApprovalLog l where l.actionDraft.actionId = :actionId order by l.decidedAt asc")
    List<ApprovalLog> findByActionId(@Param("actionId") String actionId);
}
