package com.moveinsync.pulse.web;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.moveinsync.pulse.alert.Alert;
import com.moveinsync.pulse.alert.AlertDelivery;
import com.moveinsync.pulse.alert.AlertDeliveryRepository;
import com.moveinsync.pulse.alert.AlertRepository;
import com.moveinsync.pulse.alert.AlertService;
import com.moveinsync.pulse.alert.AlertStatus;
import com.moveinsync.pulse.alert.AlertSuppression;
import com.moveinsync.pulse.alert.AlertSuppressionRepository;
import com.moveinsync.pulse.alert.dto.AcknowledgeRequest;
import com.moveinsync.pulse.alert.dto.AlertDeliveryView;
import com.moveinsync.pulse.alert.dto.AlertView;
import com.moveinsync.pulse.alert.dto.MuteRequest;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.server.ResponseStatusException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

/** In the {@code web} package so it can call TenantContext.setTenantId --
 * see the same note on ActionDraftServiceTest. */
@ExtendWith(MockitoExtension.class)
class AlertServiceTest {

    @Mock
    private AlertRepository alertRepository;
    @Mock
    private AlertDeliveryRepository alertDeliveryRepository;
    @Mock
    private AlertSuppressionRepository alertSuppressionRepository;

    private final ObjectMapper objectMapper = new ObjectMapper();

    private static Alert alert(String id, AlertStatus status) {
        return new Alert(id, "catalyst", "r_recon_critical", "ins_001", "ops", "immediate", "in_app", "fleet", "ALL",
                Instant.now(), "scan_1", status, null);
    }

    private AlertService serviceForTenant(String tenantId) {
        TenantContext tenantContext = new TenantContext();
        tenantContext.setTenantId(tenantId);
        return new AlertService(alertRepository, alertDeliveryRepository, alertSuppressionRepository, tenantContext,
                objectMapper);
    }

    @Test
    void listFiltersByStatusAndPersona() {
        when(alertRepository.findByTenantIdOrderByFiredAtDesc("catalyst")).thenReturn(List.of(
                alert("alrt_1", AlertStatus.NEW),
                alert("alrt_2", AlertStatus.ACKNOWLEDGED)));

        List<AlertView> newOnly = serviceForTenant("catalyst").list("NEW", null);

        assertThat(newOnly).extracting(AlertView::alertId).containsExactly("alrt_1");
    }

    @Test
    void acknowledgeSetsStatusAndNote() {
        Alert alert = alert("alrt_1", AlertStatus.NEW);
        when(alertRepository.findByAlertIdAndTenantId("alrt_1", "catalyst")).thenReturn(Optional.of(alert));

        AlertView result = serviceForTenant("catalyst").acknowledge("alrt_1", new AcknowledgeRequest("looked into it"));

        assertThat(result.status()).isEqualTo(AlertStatus.ACKNOWLEDGED);
        assertThat(result.acknowledgedNote()).isEqualTo("looked into it");
        assertThat(alert.status()).isEqualTo(AlertStatus.ACKNOWLEDGED);
    }

    @Test
    void muteSetsStatusAndWritesASuppressionRow() {
        Alert alert = alert("alrt_1", AlertStatus.NEW);
        when(alertRepository.findByAlertIdAndTenantId("alrt_1", "catalyst")).thenReturn(Optional.of(alert));

        AlertView result = serviceForTenant("catalyst").mute("alrt_1", new MuteRequest("noisy vendor", 7));

        assertThat(result.status()).isEqualTo(AlertStatus.MUTED);
        ArgumentCaptor<AlertSuppression> captor = ArgumentCaptor.forClass(AlertSuppression.class);
        org.mockito.Mockito.verify(alertSuppressionRepository).save(captor.capture());
        AlertSuppression suppression = captor.getValue();
        assertThat(suppression.ruleId()).isEqualTo("r_recon_critical");
        assertThat(suppression.entityDim()).isEqualTo("fleet");
        assertThat(suppression.entityValue()).isEqualTo("ALL");
        assertThat(suppression.reason()).isEqualTo("noisy vendor");
        assertThat(suppression.suppressedUntil()).isAfter(Instant.now().plusSeconds(6 * 24 * 3600));
    }

    @Test
    void getDeliveryDeserializesWouldSendTo() {
        when(alertRepository.findByAlertIdAndTenantId("alrt_1", "catalyst"))
                .thenReturn(Optional.of(alert("alrt_1", AlertStatus.NEW)));
        AlertDelivery delivery = new AlertDelivery("adlv_1", "catalyst", "alrt_1", "in_app", "Alert: subject",
                "body", "[{\"persona\":\"ops\",\"name\":\"Ops on-call\",\"email\":\"ops@catalyst.example.com\"}]",
                Instant.now(), "LOGGED");
        when(alertDeliveryRepository.findByAlertIdAndTenantId("alrt_1", "catalyst")).thenReturn(Optional.of(delivery));

        AlertDeliveryView view = serviceForTenant("catalyst").getDelivery("alrt_1");

        assertThat(view.wouldSendTo()).hasSize(1);
        assertThat(view.wouldSendTo().get(0).email()).isEqualTo("ops@catalyst.example.com");
    }

    @Test
    void anotherTenantsAlertIs404() {
        when(alertRepository.findByAlertIdAndTenantId("alrt_1", "orbit")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> serviceForTenant("orbit").acknowledge("alrt_1", AcknowledgeRequest.empty()))
                .isInstanceOf(ResponseStatusException.class);
    }
}
