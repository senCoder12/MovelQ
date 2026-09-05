package com.moveinsync.pulse.web;

import java.util.List;
import java.util.Optional;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.moveinsync.pulse.action.ActionDraft;
import com.moveinsync.pulse.action.ActionDraftRepository;
import com.moveinsync.pulse.action.ActionDraftService;
import com.moveinsync.pulse.action.ActionStatus;
import com.moveinsync.pulse.action.ApprovalLogRepository;
import com.moveinsync.pulse.action.dto.ActionDraftResponse;
import com.moveinsync.pulse.action.dto.AgentActionDraftResponse;
import com.moveinsync.pulse.action.dto.ApproveRequest;
import com.moveinsync.pulse.action.dto.FactCited;
import com.moveinsync.pulse.action.dto.Preview;
import com.moveinsync.pulse.action.dto.Recipient;
import com.moveinsync.pulse.action.dto.RejectRequest;
import com.moveinsync.pulse.agent.InsightAgentClient;
import com.moveinsync.pulse.agent.dto.DataQuality;
import com.moveinsync.pulse.agent.dto.Impact;
import com.moveinsync.pulse.agent.dto.InsightEntity;
import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.agent.dto.Metric;
import com.moveinsync.pulse.agent.dto.Narrative;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.server.ResponseStatusException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

/** In the {@code web} package (not {@code action}, where the class under
 * test lives) solely so this test can call TenantContext.setTenantId --
 * package-private on purpose, since only TenantFilter is meant to set it in
 * production. */
@ExtendWith(MockitoExtension.class)
class ActionDraftServiceTest {

    @Mock
    private InsightAgentClient agentClient;
    @Mock
    private ActionDraftRepository draftRepository;
    @Mock
    private ApprovalLogRepository approvalLogRepository;

    private final TenantScopeFilter tenantScopeFilter = new TenantScopeFilter();
    private final ObjectMapper objectMapper = new ObjectMapper();

    private static InsightPacket insight(String id) {
        return new InsightPacket(
                id,
                new Metric("delay_reconciliation_gap", "Delay reconciliation gap", 54.5, "%", 215885, "trailing_30d"),
                new InsightEntity("fleet", "ALL", "Fleet-wide"),
                List.of(),
                List.of(),
                List.of(),
                List.of(),
                new Impact(117605, null, null),
                new DataQuality(0.0, "high"),
                92,
                List.of(),
                new Narrative(id + " headline", "", List.of()));
    }

    private static AgentActionDraftResponse agentDraft(String actionId, String insightId, String type) {
        return new AgentActionDraftResponse(
                actionId, insightId, type, "Escalate delay reporting gap to Vikram Mikhailov Travel",
                new Recipient("vendor_account_manager", "Vikram Mikhailov Travel"),
                "email", "Delay reporting discrepancy", "body text",
                List.of(new FactCited("Vendor", "Vikram Mikhailov Travel", "attribution[dim=vendor_id].value")),
                new Preview("Approving records the decision to an approval log; no email is actually sent.", true),
                "rationale text", "high");
    }

    private ActionDraftService serviceForTenant(String tenantId) {
        TenantContext tenantContext = new TenantContext();
        tenantContext.setTenantId(tenantId);
        return new ActionDraftService(agentClient, draftRepository, approvalLogRepository, tenantContext,
                tenantScopeFilter, objectMapper);
    }

    @Test
    void draftFetchesTheInsightCallsTheAgentAndPersistsAsDrafted() {
        when(agentClient.getInsight("ins_001")).thenReturn(Optional.of(insight("ins_001")));
        when(agentClient.draftAction(any(InsightPacket.class), eq("VENDOR_ESCALATION")))
                .thenReturn(agentDraft("act_001", "ins_001", "VENDOR_ESCALATION"));

        ActionDraftResponse response = serviceForTenant("tenant-a").draft("ins_001", "VENDOR_ESCALATION");

        assertThat(response.actionId()).isEqualTo("act_001");
        assertThat(response.status()).isEqualTo(ActionStatus.DRAFTED);
        assertThat(response.decision()).isNull();
        assertThat(response.factsCited()).hasSize(1);
        assertThat(response.recipient().name()).isEqualTo("Vikram Mikhailov Travel");
    }

    @Test
    void draftMapsAnInapplicableTypeToA400() {
        when(agentClient.getInsight("ins_002")).thenReturn(Optional.of(insight("ins_002")));
        when(agentClient.draftAction(any(InsightPacket.class), eq("VENDOR_ESCALATION")))
                .thenThrow(HttpClientErrorException.create(
                        HttpStatus.BAD_REQUEST, "Bad Request", HttpHeaders.EMPTY, new byte[0], null));

        ActionDraftService service = serviceForTenant("tenant-a");

        assertThatThrownBy(() -> service.draft("ins_002", "VENDOR_ESCALATION"))
                .isInstanceOf(ResponseStatusException.class)
                .hasFieldOrPropertyWithValue("statusCode", HttpStatus.BAD_REQUEST);
    }

    @Test
    void approveWithNoEditGoesToApprovedAndLogsTheDecision() {
        ActionDraft draft = new ActionDraft("act_001", "tenant-a", "ins_001", "VENDOR_ESCALATION", "title",
                "{\"role\":\"vendor_account_manager\",\"name\":\"Vikram Mikhailov Travel\"}", "email", "subject",
                "body", "[]", "{\"what_changes\":\"x\",\"reversible\":true}", "rationale", "high",
                ActionStatus.DRAFTED, java.time.Instant.now());
        when(draftRepository.findByActionIdAndTenantId("act_001", "tenant-a")).thenReturn(Optional.of(draft));

        ActionDraftResponse response = serviceForTenant("tenant-a")
                .approve("act_001", new ApproveRequest("looks good", null, null));

        assertThat(response.status()).isEqualTo(ActionStatus.APPROVED);
        assertThat(response.decision().decision()).isEqualTo("APPROVED");
        assertThat(response.decision().editedBody()).isNull();
        assertThat(draft.status()).isEqualTo(ActionStatus.APPROVED);
    }

    @Test
    void approveWithAnEditedBodyGoesToEditedApprovedAndPreservesTheOriginalDraft() {
        String originalBody = "original agent-drafted body";
        ActionDraft draft = new ActionDraft("act_001", "tenant-a", "ins_001", "VENDOR_ESCALATION", "title",
                "{\"role\":\"vendor_account_manager\",\"name\":\"Vikram Mikhailov Travel\"}", "email", "subject",
                originalBody, "[]", "{\"what_changes\":\"x\",\"reversible\":true}", "rationale", "high",
                ActionStatus.DRAFTED, java.time.Instant.now());
        when(draftRepository.findByActionIdAndTenantId("act_001", "tenant-a")).thenReturn(Optional.of(draft));

        ActionDraftResponse response = serviceForTenant("tenant-a")
                .approve("act_001", new ApproveRequest(null, null, "edited body text"));

        assertThat(response.status()).isEqualTo(ActionStatus.EDITED_APPROVED);
        assertThat(response.body()).isEqualTo(originalBody);
        assertThat(response.decision().editedBody()).isEqualTo("edited body text");
    }

    @Test
    void rejectRecordsTheReasonAndSetsStatusToRejected() {
        ActionDraft draft = new ActionDraft("act_001", "tenant-a", "ins_001", "VENDOR_ESCALATION", "title",
                "{\"role\":\"vendor_account_manager\",\"name\":\"Vikram Mikhailov Travel\"}", "email", "subject",
                "body", "[]", "{\"what_changes\":\"x\",\"reversible\":true}", "rationale", "high",
                ActionStatus.DRAFTED, java.time.Instant.now());
        when(draftRepository.findByActionIdAndTenantId("act_001", "tenant-a")).thenReturn(Optional.of(draft));

        ActionDraftResponse response = serviceForTenant("tenant-a")
                .reject("act_001", new RejectRequest("Wrong vendor named"));

        assertThat(response.status()).isEqualTo(ActionStatus.REJECTED);
        assertThat(response.decision().decision()).isEqualTo("REJECTED");
        assertThat(response.decision().note()).isEqualTo("Wrong vendor named");
    }

    @Test
    void approveOnAnotherTenantsActionIs404() {
        when(draftRepository.findByActionIdAndTenantId(anyString(), eq("tenant-b"))).thenReturn(Optional.empty());
        ActionDraftService service = serviceForTenant("tenant-b");

        assertThatThrownBy(() -> service.approve("act_001", ApproveRequest.empty()))
                .isInstanceOf(ResponseStatusException.class)
                .hasFieldOrPropertyWithValue("statusCode", HttpStatus.NOT_FOUND);
    }
}
