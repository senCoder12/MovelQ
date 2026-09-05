package com.moveinsync.pulse.job;

import java.util.List;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ScanRunRepository extends JpaRepository<ScanRun, String> {

    List<ScanRun> findByTenantIdOrderByStartedAtDesc(String tenantId, Pageable pageable);
}
