package com.moveinsync.pulse.report;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

public interface ReportRecipientRepository extends JpaRepository<ReportRecipient, String> {

    List<ReportRecipient> findByTenantIdOrderByRoleAscNameAsc(String tenantId);

    List<ReportRecipient> findByTenantIdAndRecipientIdIn(String tenantId, List<String> recipientIds);

    Optional<ReportRecipient> findByRecipientIdAndTenantId(String recipientId, String tenantId);
}
