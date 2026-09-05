package com.moveinsync.pulse.job;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.stream.Collectors;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.moveinsync.pulse.action.ActionDraft;
import com.moveinsync.pulse.action.ActionDraftRepository;
import com.moveinsync.pulse.agent.InsightAgentClient;
import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.alert.Alert;
import com.moveinsync.pulse.alert.AlertDelivery;
import com.moveinsync.pulse.alert.AlertDeliveryRepository;
import com.moveinsync.pulse.alert.AlertRepository;
import com.moveinsync.pulse.alert.AlertStatus;
import com.moveinsync.pulse.alert.AlertSuppression;
import com.moveinsync.pulse.alert.AlertSuppressionRepository;
import com.moveinsync.pulse.alert.PersonaRecipients;
import com.moveinsync.pulse.alert.dto.AlertCandidate;
import com.moveinsync.pulse.alert.dto.EvaluateAlertsRequest;
import com.moveinsync.pulse.alert.dto.EvaluateAlertsResponse;
import com.moveinsync.pulse.web.TenantScopeFilter;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;

/**
 * The scan: fetch this tenant's insights, ask the agent which alert rules
 * fire against them (agent/app/detect/alert_router.py -- pure rule
 * matching, ranked and deduped before evaluation, no LLM call anywhere in
 * this path), apply cooldown and suppression, render and persist whatever
 * survives, then persist one scan_run row recording what happened.
 *
 * This is a deliberately minimal stand-in for a real job runner: on-demand
 * only (JobController's endpoint, or once per tenant at startup via
 * ScanStartupRunner), not a scheduler -- no @Scheduled, no background
 * thread pool, no retries of a failed scan. A production version would add
 * scheduling around this method; nothing about the method itself would
 * need to change.
 */
@Service
public class ScanService {

    private static final Logger log = LoggerFactory.getLogger(ScanService.class);

    private static final String IMMEDIATE_URGENCY = "immediate";
    private static final Duration REPEAT_AFTER = Duration.ofHours(24);

    private final InsightAgentClient agentClient;
    private final TenantScopeFilter tenantScopeFilter;
    private final ActionDraftRepository actionDraftRepository;
    private final AlertRepository alertRepository;
    private final AlertDeliveryRepository alertDeliveryRepository;
    private final AlertSuppressionRepository alertSuppressionRepository;
    private final ScanRunRepository scanRunRepository;
    private final ObjectMapper objectMapper;

    public ScanService(InsightAgentClient agentClient, TenantScopeFilter tenantScopeFilter,
            ActionDraftRepository actionDraftRepository, AlertRepository alertRepository,
            AlertDeliveryRepository alertDeliveryRepository, AlertSuppressionRepository alertSuppressionRepository,
            ScanRunRepository scanRunRepository, ObjectMapper objectMapper) {
        this.agentClient = agentClient;
        this.tenantScopeFilter = tenantScopeFilter;
        this.actionDraftRepository = actionDraftRepository;
        this.alertRepository = alertRepository;
        this.alertDeliveryRepository = alertDeliveryRepository;
        this.alertSuppressionRepository = alertSuppressionRepository;
        this.scanRunRepository = scanRunRepository;
        this.objectMapper = objectMapper;
    }

    public ScanRunView runForTenant(String tenantId) {
        Instant startedAt = Instant.now();
        ScanRun run = new ScanRun("scan_" + UUID.randomUUID(), tenantId, startedAt);
        scanRunRepository.save(run);

        List<InsightPacket> insights;
        EvaluateAlertsResponse evaluation;
        try {
            insights = tenantScopeFilter.apply(agentClient.listInsights(tenantId), tenantId);
            evaluation = agentClient.evaluateAlerts(
                    new EvaluateAlertsRequest(insights, knownEntities(tenantId)));
        } catch (RestClientException ex) {
            log.warn("Scan failed for tenant {}: {}", tenantId, ex.getMessage());
            run.complete(ScanRunStatus.FAILED, Instant.now(), 0, 0, 0, 0, ex.getMessage());
            scanRunRepository.save(run);
            return ScanRunView.of(run);
        }

        Map<String, InsightPacket> insightsById = insights.stream()
                .collect(Collectors.toMap(InsightPacket::insightId, insight -> insight, (a, b) -> a, LinkedHashMap::new));

        int fired = 0;
        int suppressed = 0;
        for (AlertCandidate candidate : evaluation.candidates()) {
            InsightPacket insight = insightsById.get(candidate.insightId());
            if (insight == null) {
                continue;
            }
            if (isSuppressed(tenantId, candidate) || isInCooldown(tenantId, candidate)) {
                suppressed++;
                continue;
            }
            fireAlert(tenantId, run.scanRunId(), candidate, insight);
            fired++;
        }

        int repeated = repeatUnacknowledgedImmediateAlerts(tenantId, run.scanRunId());

        run.complete(ScanRunStatus.SUCCESS, Instant.now(), evaluation.rankedInsightIds().size(), fired, suppressed,
                repeated, null);
        scanRunRepository.save(run);
        return ScanRunView.of(run);
    }

    private List<List<String>> knownEntities(String tenantId) {
        List<List<String>> pairs = new ArrayList<>();
        for (Alert alert : alertRepository.findByTenantIdOrderByFiredAtDesc(tenantId)) {
            List<String> pair = List.of(alert.entityDim(), alert.entityValue());
            if (!pairs.contains(pair)) {
                pairs.add(pair);
            }
        }
        return pairs;
    }

    private boolean isSuppressed(String tenantId, AlertCandidate candidate) {
        return alertSuppressionRepository
                .findFirstByTenantIdAndRuleIdAndEntityDimAndEntityValueAndSuppressedUntilAfterOrderBySuppressedUntilDesc(
                        tenantId, candidate.ruleId(), candidate.entityDim(), candidate.entityValue(), Instant.now())
                .isPresent();
    }

    private boolean isInCooldown(String tenantId, AlertCandidate candidate) {
        return alertRepository
                .findFirstByTenantIdAndRuleIdAndEntityDimAndEntityValueOrderByFiredAtDesc(
                        tenantId, candidate.ruleId(), candidate.entityDim(), candidate.entityValue())
                .filter(previous -> Duration.between(previous.firedAt(), Instant.now())
                        .compareTo(Duration.ofHours(candidate.cooldownHours())) < 0)
                .isPresent();
    }

    private void fireAlert(String tenantId, String scanRunId, AlertCandidate candidate, InsightPacket insight) {
        Instant now = Instant.now();
        Alert alert = new Alert(
                "alrt_" + UUID.randomUUID(), tenantId, candidate.ruleId(), candidate.insightId(),
                candidate.persona(), candidate.urgency(), candidate.channel(), candidate.entityDim(),
                candidate.entityValue(), now, scanRunId, AlertStatus.NEW, null);
        alertRepository.save(alert);
        persistDelivery(alert, subjectFor(tenantId, insight), insight.narrative().body(), candidate.persona());
    }

    /** Reuses the most recent action draft's subject for this insight, if
     * one has been drafted -- that subject is already grounded and human
     * facing. Otherwise falls back to the insight's own headline, still
     * zero new prose generated (no LLM call anywhere in this path). */
    private String subjectFor(String tenantId, InsightPacket insight) {
        List<ActionDraft> drafts = actionDraftRepository
                .findByTenantIdAndInsightIdOrderByCreatedAtDesc(tenantId, insight.insightId());
        String base = drafts.isEmpty() ? insight.narrative().headline() : drafts.get(0).subject();
        return "Alert: " + base;
    }

    private int repeatUnacknowledgedImmediateAlerts(String tenantId, String scanRunId) {
        Instant cutoff = Instant.now().minus(REPEAT_AFTER);
        List<Alert> eligible = alertRepository.findByTenantIdAndStatusAndUrgencyAndFiredAtBeforeAndRepeatOfIsNull(
                tenantId, AlertStatus.NEW, IMMEDIATE_URGENCY, cutoff);

        int repeated = 0;
        for (Alert original : eligible) {
            if (alertRepository.existsByRepeatOf(original.alertId())) {
                continue;
            }
            Instant now = Instant.now();
            Alert repeat = new Alert(
                    "alrt_" + UUID.randomUUID(), tenantId, original.ruleId(), original.insightId(),
                    original.persona(), original.urgency(), original.channel(), original.entityDim(),
                    original.entityValue(), now, scanRunId, AlertStatus.NEW, original.alertId());
            alertRepository.save(repeat);

            Optional<AlertDelivery> originalDelivery = alertDeliveryRepository
                    .findByAlertIdAndTenantId(original.alertId(), tenantId);
            String subject = "Repeat: " + originalDelivery.map(AlertDelivery::renderedSubject)
                    .orElse(original.ruleId());
            String body = originalDelivery.map(AlertDelivery::renderedBody)
                    .orElse("(original delivery not found)");
            persistDelivery(repeat, subject, body, original.persona());
            repeated++;
        }
        return repeated;
    }

    private void persistDelivery(Alert alert, String subject, String body, String persona) {
        AlertDelivery delivery = new AlertDelivery(
                "adlv_" + UUID.randomUUID(), alert.tenantId(), alert.alertId(), alert.channel(), subject, body,
                toJson(List.of(PersonaRecipients.forTenant(alert.tenantId(), persona))), Instant.now(), "LOGGED");
        alertDeliveryRepository.save(delivery);
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("failed to serialize would_send_to", ex);
        }
    }
}
