package com.moveinsync.pulse.action;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

public interface ApprovalLogRepository extends JpaRepository<ApprovalLog, String> {

    Optional<ApprovalLog> findFirstByActionIdOrderByDecidedAtDesc(String actionId);
}
