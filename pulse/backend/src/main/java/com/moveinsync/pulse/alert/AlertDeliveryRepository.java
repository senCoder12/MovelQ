package com.moveinsync.pulse.alert;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

public interface AlertDeliveryRepository extends JpaRepository<AlertDelivery, String> {

    Optional<AlertDelivery> findByAlertIdAndTenantId(String alertId, String tenantId);
}
