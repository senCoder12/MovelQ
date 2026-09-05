package com.moveinsync.pulse.job;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.moveinsync.pulse.action.ActionDraftRepository;
import com.moveinsync.pulse.agent.InsightAgentClient;
import com.moveinsync.pulse.agent.dto.DataQuality;
import com.moveinsync.pulse.agent.dto.Impact;
import com.moveinsync.pulse.agent.dto.InsightEntity;
import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.agent.dto.Metric;
import com.moveinsync.pulse.agent.dto.Narrative;
import com.moveinsync.pulse.alert.Alert;
import com.moveinsync.pulse.alert.AlertDelivery;
import com.moveinsync.pulse.alert.AlertDeliveryRepository;
import com.moveinsync.pulse.alert.AlertRepository;
import com.moveinsync.pulse.alert.AlertStatus;
import com.moveinsync.pulse.alert.AlertSuppression;
import com.moveinsync.pulse.alert.AlertSuppressionRepository;
import com.moveinsync.pulse.alert.dto.AlertCandidate;
import com.moveinsync.pulse.alert.dto.EvaluateAlertsResponse;
import com.moveinsync.pulse.web.TenantScopeFilter;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ScanServiceTest {

    @Mock
    private InsightAgentClient agentClient;
    @Mock
    private ActionDraftRepository actionDraftRepository;
    @Mock
    private AlertRepository alertRepository;
    @Mock
    private AlertDeliveryRepository alertDeliveryRepository;
    @Mock
    private AlertSuppressionRepository alertSuppressionRepository;
    @Mock
    private ScanRunRepository scanRunRepository;

    private final TenantScopeFilter tenantScopeFilter = new TenantScopeFilter();
    private final ObjectMapper objectMapper = new ObjectMapper();

    private ScanService service() {
        return new ScanService(agentClient, tenantScopeFilter, actionDraftRepository, alertRepository,
                alertDeliveryRepository, alertSuppressionRepository, scanRunRepository, objectMapper);
    }

    private static InsightPacket insight(String id) {
        return new InsightPacket(
                id,
                new Metric("delay_reconciliation_gap", "Delay reconciliation gap", 92.0, "%", 215885, "trailing_30d"),
                new InsightEntity("fleet", "ALL", "Fleet-wide"),
                List.of(), List.of(), List.of(), List.of(),
                new Impact(117605, null, null),
                new DataQuality(0.0, "high"),
                92,
                List.of(),
                new Narrative(id + " headline", "body text", List.of()));
    }

    private static AlertCandidate candidate(int cooldownHours) {
        return new AlertCandidate("r_recon_critical", "ins_001", "ops", "immediate", "in_app", "fleet", "ALL",
                cooldownHours);
    }

    @Test
    void firesAnAlertForAMatchedCandidateWithNoPriorHistory() {
        when(agentClient.listInsights("catalyst")).thenReturn(List.of(insight("ins_001")));
        when(agentClient.evaluateAlerts(any()))
                .thenReturn(new EvaluateAlertsResponse(List.of(candidate(24)), List.of("ins_001")));
        when(alertRepository.findByTenantIdOrderByFiredAtDesc("catalyst")).thenReturn(List.of());
        when(alertSuppressionRepository
                .findFirstByTenantIdAndRuleIdAndEntityDimAndEntityValueAndSuppressedUntilAfterOrderBySuppressedUntilDesc(
                        eq("catalyst"), any(), any(), any(), any()))
                .thenReturn(Optional.empty());
        when(alertRepository.findFirstByTenantIdAndRuleIdAndEntityDimAndEntityValueOrderByFiredAtDesc(
                eq("catalyst"), any(), any(), any())).thenReturn(Optional.empty());
        when(alertRepository.findByTenantIdAndStatusAndUrgencyAndFiredAtBeforeAndRepeatOfIsNull(
                eq("catalyst"), eq(AlertStatus.NEW), eq("immediate"), any())).thenReturn(List.of());
        when(actionDraftRepository.findByTenantIdAndInsightIdOrderByCreatedAtDesc("catalyst", "ins_001"))
                .thenReturn(List.of());

        ScanRunView result = service().runForTenant("catalyst");

        assertThat(result.status()).isEqualTo(ScanRunStatus.SUCCESS);
        assertThat(result.alertsFired()).isEqualTo(1);
        assertThat(result.alertsSuppressed()).isZero();
        assertThat(result.alertsRepeated()).isZero();

        ArgumentCaptor<Alert> alertCaptor = ArgumentCaptor.forClass(Alert.class);
        verify(alertRepository).save(alertCaptor.capture());
        assertThat(alertCaptor.getValue().status()).isEqualTo(AlertStatus.NEW);
        assertThat(alertCaptor.getValue().ruleId()).isEqualTo("r_recon_critical");

        ArgumentCaptor<AlertDelivery> deliveryCaptor = ArgumentCaptor.forClass(AlertDelivery.class);
        verify(alertDeliveryRepository).save(deliveryCaptor.capture());
        assertThat(deliveryCaptor.getValue().renderedSubject()).contains("ins_001 headline");
        assertThat(deliveryCaptor.getValue().deliveryStatus()).isEqualTo("LOGGED");
    }

    @Test
    void skipsACandidateStillInCooldownAndCountsItAsSuppressed() {
        when(agentClient.listInsights("catalyst")).thenReturn(List.of(insight("ins_001")));
        when(agentClient.evaluateAlerts(any()))
                .thenReturn(new EvaluateAlertsResponse(List.of(candidate(24)), List.of("ins_001")));
        when(alertRepository.findByTenantIdOrderByFiredAtDesc("catalyst")).thenReturn(List.of());
        when(alertSuppressionRepository
                .findFirstByTenantIdAndRuleIdAndEntityDimAndEntityValueAndSuppressedUntilAfterOrderBySuppressedUntilDesc(
                        eq("catalyst"), any(), any(), any(), any()))
                .thenReturn(Optional.empty());

        Alert firedOneHourAgo = mock(Alert.class);
        when(firedOneHourAgo.firedAt()).thenReturn(Instant.now().minusSeconds(3600));
        when(alertRepository.findFirstByTenantIdAndRuleIdAndEntityDimAndEntityValueOrderByFiredAtDesc(
                eq("catalyst"), any(), any(), any())).thenReturn(Optional.of(firedOneHourAgo));
        when(alertRepository.findByTenantIdAndStatusAndUrgencyAndFiredAtBeforeAndRepeatOfIsNull(
                eq("catalyst"), eq(AlertStatus.NEW), eq("immediate"), any())).thenReturn(List.of());

        ScanRunView result = service().runForTenant("catalyst");

        assertThat(result.alertsFired()).isZero();
        assertThat(result.alertsSuppressed()).isEqualTo(1);
        verify(alertRepository, never()).save(any());
    }

    @Test
    void skipsAnExplicitlyMutedCandidate() {
        when(agentClient.listInsights("catalyst")).thenReturn(List.of(insight("ins_001")));
        when(agentClient.evaluateAlerts(any()))
                .thenReturn(new EvaluateAlertsResponse(List.of(candidate(24)), List.of("ins_001")));
        when(alertRepository.findByTenantIdOrderByFiredAtDesc("catalyst")).thenReturn(List.of());

        AlertSuppression suppression = mock(AlertSuppression.class);
        when(alertSuppressionRepository
                .findFirstByTenantIdAndRuleIdAndEntityDimAndEntityValueAndSuppressedUntilAfterOrderBySuppressedUntilDesc(
                        eq("catalyst"), any(), any(), any(), any()))
                .thenReturn(Optional.of(suppression));
        when(alertRepository.findByTenantIdAndStatusAndUrgencyAndFiredAtBeforeAndRepeatOfIsNull(
                eq("catalyst"), eq(AlertStatus.NEW), eq("immediate"), any())).thenReturn(List.of());

        ScanRunView result = service().runForTenant("catalyst");

        assertThat(result.alertsFired()).isZero();
        assertThat(result.alertsSuppressed()).isEqualTo(1);
        verify(alertRepository, never()).save(any());
        // A muted candidate is never even checked for cooldown -- suppression short-circuits first.
        verify(alertRepository, never())
                .findFirstByTenantIdAndRuleIdAndEntityDimAndEntityValueOrderByFiredAtDesc(any(), any(), any(), any());
    }

    @Test
    void reRaisesAnOldUnacknowledgedImmediateAlertExactlyOnce() {
        when(agentClient.listInsights("catalyst")).thenReturn(List.of());
        when(agentClient.evaluateAlerts(any())).thenReturn(new EvaluateAlertsResponse(List.of(), List.of()));
        when(alertRepository.findByTenantIdOrderByFiredAtDesc("catalyst")).thenReturn(List.of());

        Alert original = new Alert("alrt_original", "catalyst", "r_recon_critical", "ins_001", "ops", "immediate",
                "in_app", "fleet", "ALL", Instant.now().minusSeconds(25 * 3600), "scan_prev", AlertStatus.NEW, null);
        when(alertRepository.findByTenantIdAndStatusAndUrgencyAndFiredAtBeforeAndRepeatOfIsNull(
                eq("catalyst"), eq(AlertStatus.NEW), eq("immediate"), any())).thenReturn(List.of(original));
        when(alertRepository.existsByRepeatOf("alrt_original")).thenReturn(false);
        when(alertDeliveryRepository.findByAlertIdAndTenantId("alrt_original", "catalyst")).thenReturn(Optional.empty());

        ScanRunView result = service().runForTenant("catalyst");

        assertThat(result.alertsRepeated()).isEqualTo(1);
        ArgumentCaptor<Alert> alertCaptor = ArgumentCaptor.forClass(Alert.class);
        verify(alertRepository, times(1)).save(alertCaptor.capture());
        assertThat(alertCaptor.getValue().repeatOf()).isEqualTo("alrt_original");
    }

    @Test
    void doesNotReRaiseAnAlertThatHasAlreadyBeenRepeatedOnce() {
        when(agentClient.listInsights("catalyst")).thenReturn(List.of());
        when(agentClient.evaluateAlerts(any())).thenReturn(new EvaluateAlertsResponse(List.of(), List.of()));
        when(alertRepository.findByTenantIdOrderByFiredAtDesc("catalyst")).thenReturn(List.of());

        Alert original = new Alert("alrt_original", "catalyst", "r_recon_critical", "ins_001", "ops", "immediate",
                "in_app", "fleet", "ALL", Instant.now().minusSeconds(25 * 3600), "scan_prev", AlertStatus.NEW, null);
        when(alertRepository.findByTenantIdAndStatusAndUrgencyAndFiredAtBeforeAndRepeatOfIsNull(
                eq("catalyst"), eq(AlertStatus.NEW), eq("immediate"), any())).thenReturn(List.of(original));
        when(alertRepository.existsByRepeatOf("alrt_original")).thenReturn(true);

        ScanRunView result = service().runForTenant("catalyst");

        assertThat(result.alertsRepeated()).isZero();
        verify(alertRepository, never()).save(any());
    }
}
