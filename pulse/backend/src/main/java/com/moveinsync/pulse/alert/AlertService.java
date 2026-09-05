package com.moveinsync.pulse.alert;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.UUID;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.moveinsync.pulse.alert.dto.AcknowledgeRequest;
import com.moveinsync.pulse.alert.dto.AlertDeliveryView;
import com.moveinsync.pulse.alert.dto.AlertView;
import com.moveinsync.pulse.alert.dto.MuteRequest;
import com.moveinsync.pulse.alert.dto.PersonaRecipient;
import com.moveinsync.pulse.web.TenantContext;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

/** The read/decide half of alerting -- listing, acknowledging and muting.
 * Firing new alerts is ScanService's job (it owns the scan and the rule
 * evaluation); this class only ever changes a NEW alert into
 * ACKNOWLEDGED or MUTED, one at a time, per the same "no bulk, no
 * auto-approve" spirit as action approval. */
@Service
public class AlertService {

    /** No auth/user model exists anywhere in this app yet -- same
     * placeholder as ActionDraftService.DECIDED_BY. */
    private static final String DECIDED_BY = "operator";

    private final AlertRepository alertRepository;
    private final AlertDeliveryRepository alertDeliveryRepository;
    private final AlertSuppressionRepository alertSuppressionRepository;
    private final TenantContext tenantContext;
    private final ObjectMapper objectMapper;

    public AlertService(AlertRepository alertRepository, AlertDeliveryRepository alertDeliveryRepository,
            AlertSuppressionRepository alertSuppressionRepository, TenantContext tenantContext,
            ObjectMapper objectMapper) {
        this.alertRepository = alertRepository;
        this.alertDeliveryRepository = alertDeliveryRepository;
        this.alertSuppressionRepository = alertSuppressionRepository;
        this.tenantContext = tenantContext;
        this.objectMapper = objectMapper;
    }

    public List<AlertView> list(String status, String persona) {
        return alertRepository.findByTenantIdOrderByFiredAtDesc(tenantContext.tenantId()).stream()
                .filter(alert -> status == null || status.isBlank() || alert.status().name().equalsIgnoreCase(status))
                .filter(alert -> persona == null || persona.isBlank() || alert.persona().equalsIgnoreCase(persona))
                .map(AlertView::of)
                .toList();
    }

    public AlertView acknowledge(String alertId, AcknowledgeRequest request) {
        Alert alert = findOwned(alertId);
        alert.acknowledge(Instant.now(), DECIDED_BY, request.note());
        alertRepository.save(alert);
        return AlertView.of(alert);
    }

    public AlertView mute(String alertId, MuteRequest request) {
        Alert alert = findOwned(alertId);
        alert.mute();
        alertRepository.save(alert);

        Instant now = Instant.now();
        AlertSuppression suppression = new AlertSuppression(
                "asup_" + UUID.randomUUID(),
                alert.tenantId(),
                alert.ruleId(),
                alert.entityDim(),
                alert.entityValue(),
                now.plus(request.days(), ChronoUnit.DAYS),
                request.reason(),
                DECIDED_BY,
                now);
        alertSuppressionRepository.save(suppression);

        return AlertView.of(alert);
    }

    public AlertDeliveryView getDelivery(String alertId) {
        Alert alert = findOwned(alertId);
        AlertDelivery delivery = alertDeliveryRepository.findByAlertIdAndTenantId(alertId, alert.tenantId())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        return new AlertDeliveryView(
                delivery.deliveryId(),
                delivery.alertId(),
                delivery.channel(),
                delivery.renderedSubject(),
                delivery.renderedBody(),
                fromJson(delivery.wouldSendToJson()),
                delivery.createdAt(),
                delivery.deliveryStatus());
    }

    private Alert findOwned(String alertId) {
        return alertRepository.findByAlertIdAndTenantId(alertId, tenantContext.tenantId())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
    }

    private List<PersonaRecipient> fromJson(String json) {
        try {
            return objectMapper.readValue(json, new TypeReference<List<PersonaRecipient>>() {
            });
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("failed to deserialize would_send_to", ex);
        }
    }
}
