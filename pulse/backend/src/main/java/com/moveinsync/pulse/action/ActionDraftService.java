package com.moveinsync.pulse.action;

import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.moveinsync.pulse.action.dto.ActionDraftResponse;
import com.moveinsync.pulse.action.dto.AgentActionDraftResponse;
import com.moveinsync.pulse.action.dto.ApprovalDecisionView;
import com.moveinsync.pulse.action.dto.ApproveRequest;
import com.moveinsync.pulse.action.dto.FactCited;
import com.moveinsync.pulse.action.dto.Preview;
import com.moveinsync.pulse.action.dto.Recipient;
import com.moveinsync.pulse.action.dto.RejectRequest;
import com.moveinsync.pulse.agent.InsightAgentClient;
import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.web.TenantContext;
import com.moveinsync.pulse.web.TenantScopeFilter;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

/** Drafting, listing and per-action approval/rejection. The only place an
 * ActionDraft's status ever changes -- approve/reject are per-action and
 * explicit, there is no bulk or threshold-based path here at all.
 *
 * "Execute" in this prototype means writing an ApprovalLog row: nothing here
 * calls a vendor system or sends anything, whatever the action's channel
 * says (see AgentActionDraftResponse.preview / drafters.py's docstring). */
@Service
public class ActionDraftService {

    /** No auth/user model exists yet anywhere in this app (TenantContext is
     * the only identity concept there is) -- every decision is attributed to
     * this placeholder until one lands. */
    private static final String DECIDED_BY = "operator";

    private final InsightAgentClient agentClient;
    private final ActionDraftRepository draftRepository;
    private final ApprovalLogRepository approvalLogRepository;
    private final TenantContext tenantContext;
    private final TenantScopeFilter tenantScopeFilter;
    private final ObjectMapper objectMapper;

    public ActionDraftService(InsightAgentClient agentClient, ActionDraftRepository draftRepository,
            ApprovalLogRepository approvalLogRepository, TenantContext tenantContext,
            TenantScopeFilter tenantScopeFilter, ObjectMapper objectMapper) {
        this.agentClient = agentClient;
        this.draftRepository = draftRepository;
        this.approvalLogRepository = approvalLogRepository;
        this.tenantContext = tenantContext;
        this.tenantScopeFilter = tenantScopeFilter;
        this.objectMapper = objectMapper;
    }

    public ActionDraftResponse draft(String insightId, String type) {
        InsightPacket insight = fetchOwnedInsight(insightId);

        AgentActionDraftResponse agentDraft;
        try {
            agentDraft = agentClient.draftAction(insight, type);
        } catch (HttpClientErrorException.BadRequest ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "action type not applicable to this insight", ex);
        } catch (RestClientException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "agent unavailable", ex);
        }

        ActionDraft entity = new ActionDraft(
                agentDraft.actionId(),
                tenantContext.tenantId(),
                agentDraft.insightId(),
                agentDraft.type(),
                agentDraft.title(),
                toJson(agentDraft.recipient()),
                agentDraft.channel(),
                agentDraft.subject(),
                agentDraft.body(),
                toJson(agentDraft.factsCited()),
                toJson(agentDraft.preview()),
                agentDraft.rationale(),
                agentDraft.confidence(),
                ActionStatus.DRAFTED,
                Instant.now());
        draftRepository.save(entity);
        return toResponse(entity, null);
    }

    public List<ActionDraftResponse> listForInsight(String insightId) {
        return draftRepository.findByTenantIdAndInsightIdOrderByCreatedAtDesc(tenantContext.tenantId(), insightId)
                .stream().map(this::toResponseWithDecision).toList();
    }

    public List<ActionDraftResponse> audit(String status) {
        String tenantId = tenantContext.tenantId();
        List<ActionDraft> drafts = (status == null || status.isBlank())
                ? draftRepository.findByTenantIdOrderByCreatedAtDesc(tenantId)
                : draftRepository.findByTenantIdAndStatusOrderByCreatedAtDesc(tenantId, parseStatus(status));
        return drafts.stream().map(this::toResponseWithDecision).toList();
    }

    public ActionDraftResponse approve(String actionId, ApproveRequest request) {
        ActionDraft draft = findOwned(actionId);
        boolean edited = hasText(request.editedSubject()) || hasText(request.editedBody());
        ActionStatus newStatus = edited ? ActionStatus.EDITED_APPROVED : ActionStatus.APPROVED;

        draft.setStatus(newStatus);
        draftRepository.save(draft);

        ApprovalLog log = new ApprovalLog("log_" + UUID.randomUUID(), draft.tenantId(), actionId, newStatus.name(),
                DECIDED_BY, Instant.now(), request.editedSubject(), request.editedBody(), request.note());
        approvalLogRepository.save(log);

        return toResponse(draft, log);
    }

    public ActionDraftResponse reject(String actionId, RejectRequest request) {
        ActionDraft draft = findOwned(actionId);
        draft.setStatus(ActionStatus.REJECTED);
        draftRepository.save(draft);

        ApprovalLog log = new ApprovalLog("log_" + UUID.randomUUID(), draft.tenantId(), actionId,
                ActionStatus.REJECTED.name(), DECIDED_BY, Instant.now(), null, null, request.reason());
        approvalLogRepository.save(log);

        return toResponse(draft, log);
    }

    private InsightPacket fetchOwnedInsight(String insightId) {
        InsightPacket insight;
        try {
            insight = agentClient.getInsight(insightId)
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        } catch (RestClientException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "agent unavailable", ex);
        }
        if (!tenantScopeFilter.matchesTenant(insight, tenantContext.tenantId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        }
        return insight;
    }

    private ActionDraft findOwned(String actionId) {
        return draftRepository.findByActionIdAndTenantId(actionId, tenantContext.tenantId())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
    }

    private ActionDraftResponse toResponseWithDecision(ActionDraft draft) {
        ApprovalLog log = approvalLogRepository.findFirstByActionIdOrderByDecidedAtDesc(draft.actionId()).orElse(null);
        return toResponse(draft, log);
    }

    private ActionDraftResponse toResponse(ActionDraft draft, ApprovalLog log) {
        return new ActionDraftResponse(
                draft.actionId(), draft.insightId(), draft.type(), draft.title(),
                fromJson(draft.recipientJson(), Recipient.class),
                draft.channel(), draft.subject(), draft.body(),
                fromJsonList(draft.factsCitedJson()),
                fromJson(draft.previewJson(), Preview.class),
                draft.rationale(), draft.confidence(), draft.status(), draft.createdAt(),
                log == null ? null : new ApprovalDecisionView(log.decision(), log.decidedBy(), log.decidedAt(),
                        log.editedSubject(), log.editedBody(), log.note()));
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("failed to serialize action draft field", ex);
        }
    }

    private <T> T fromJson(String json, Class<T> type) {
        try {
            return objectMapper.readValue(json, type);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("failed to deserialize action draft field", ex);
        }
    }

    private List<FactCited> fromJsonList(String json) {
        try {
            return objectMapper.readValue(json, new TypeReference<List<FactCited>>() {
            });
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("failed to deserialize action draft field", ex);
        }
    }

    private static boolean hasText(String value) {
        return value != null && !value.isBlank();
    }

    private static ActionStatus parseStatus(String status) {
        try {
            return ActionStatus.valueOf(status.toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "unknown status: " + status, ex);
        }
    }
}
