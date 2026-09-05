package com.moveinsync.pulse.action;

import java.util.List;
import java.util.Map;

import com.moveinsync.pulse.action.ActionDraft.FactCitation;
import com.moveinsync.pulse.insight.Insight;
import com.moveinsync.pulse.insight.InsightRepository;
import com.moveinsync.pulse.tenant.MissingTenantException;
import com.moveinsync.pulse.tenant.TenantContextHolder;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Covers the action tables: the JSONB columns round-trip, and the same tenant filter
 * applies here as to insights.
 *
 * <p>The JSONB assertion is the point. {@code recipient}, {@code facts_cited},
 * {@code preview} and {@code params} are real jsonb, not text, and they are mapped to typed
 * Java rather than to a String -- so a mapping that only appears to work would show up as a
 * serialisation failure here rather than as an empty panel in the demo.
 */
@SpringBootTest
@Transactional
class ActionDraftRepositoryTest {

    private static final String CATALYST = "catalyst";
    private static final String VANTA = "vanta";

    @Autowired
    private ActionDraftRepository actionDrafts;

    @Autowired
    private ApprovalLogRepository approvalLogs;

    @Autowired
    private InsightRepository insights;

    @Autowired
    private JdbcTemplate jdbc;

    @Test
    @DisplayName("JSONB columns survive the round trip as typed Java")
    void jsonbColumnsRoundTrip() {
        insertInsight(CATALYST, "act_test_insight");
        TenantContextHolder.set(CATALYST);

        Insight insight = insights.findByInsightId("act_test_insight").orElseThrow();
        ActionDraft draft = new ActionDraft(insight, "act_test_1", "ticket",
                "Audit EV-contract billing", "1,044 trips billed under EV contract terms.",
                "Direct billing exposure.");
        draft.setRecipient(Map.of("channel", "jira", "project", "FIN"));
        draft.setFactsCited(List.of(
                new FactCitation("metric.value", "EV contract mismatch rate", 12.39, "%"),
                new FactCitation("impact.affected_trips", "mismatched trips", 1044, "trips")));
        draft.setPreview(Map.of("subject", "[Pulse] EV-contract trips on petrol/diesel"));
        draft.setParams(Map.of("priority", "P1"));
        actionDrafts.saveAndFlush(draft);

        ActionDraft reloaded = actionDrafts.findByActionId("act_test_1").orElseThrow();
        assertThat(reloaded.getRecipient()).containsEntry("channel", "jira").containsEntry("project", "FIN");
        assertThat(reloaded.getPreview()).containsEntry("subject", "[Pulse] EV-contract trips on petrol/diesel");
        assertThat(reloaded.getParams()).containsEntry("priority", "P1");
        assertThat(reloaded.getFactsCited()).hasSize(2);
        assertThat(reloaded.getFactsCited().get(0).label()).isEqualTo("EV contract mismatch rate");
        assertThat(reloaded.getFactsCited().get(0).field()).isEqualTo("metric.value");
        assertThat(reloaded.getStatus()).isEqualTo(ActionDraft.STATUS_DRAFT);
        assertThat(reloaded.getTenantId()).isEqualTo(CATALYST);
        assertThat(reloaded.getCreatedAt()).isNotNull();

        // Confirm it really is jsonb in the database, not text that happens to parse.
        String channel = jdbc.queryForObject(
                "select recipient ->> 'channel' from action_draft where tenant_id = ? and action_id = ?",
                String.class, CATALYST, "act_test_1");
        assertThat(channel).isEqualTo("jira");
    }

    @Test
    @DisplayName("action drafts and approvals are tenant-scoped like everything else")
    void actionsAreTenantScoped() {
        insertInsight(CATALYST, "act_scope_insight");
        insertInsight(VANTA, "act_scope_insight");
        insertActionDraft(CATALYST, "act_scope", "act_scope_insight");
        insertActionDraft(VANTA, "act_scope", "act_scope_insight");

        TenantContextHolder.set(CATALYST);
        ActionDraft catalystDraft = actionDrafts.findByActionId("act_scope").orElseThrow();
        assertThat(catalystDraft.getTenantId()).isEqualTo(CATALYST);
        assertThat(catalystDraft.getTitle()).isEqualTo("title for " + CATALYST);

        TenantContextHolder.set(VANTA);
        ActionDraft vantaDraft = actionDrafts.findByActionId("act_scope").orElseThrow();
        assertThat(vantaDraft.getTitle()).isEqualTo("title for " + VANTA);
        assertThat(vantaDraft.getId()).isNotEqualTo(catalystDraft.getId());

        // The other tenant's draft is not reachable by primary key either.
        TenantContextHolder.set(CATALYST);
        assertThat(actionDrafts.findById(vantaDraft.getId())).isEmpty();

        TenantContextHolder.clear();
        assertThatThrownBy(() -> approvalLogs.findByActionId("act_scope"))
                .isInstanceOf(MissingTenantException.class);
    }

    private void insertInsight(String tenantId, String insightId) {
        jdbc.update("""
                insert into insight (
                    tenant_id, insight_id, severity,
                    metric_id, metric_name, metric_value, metric_unit, metric_n, metric_window,
                    entity_dim, entity_ref, entity_name,
                    data_quality_excluded_pct, data_quality_confidence,
                    narrative_headline, narrative_body)
                values (?, ?, 50, 'action_metric', 'Action metric', 1.0, '%', 1, 'trailing_30d',
                        'fleet', 'ALL', 'Fleet-wide', 0.0, 'high', 'headline', 'body')
                """, tenantId, insightId);
    }

    private void insertActionDraft(String tenantId, String actionId, String insightId) {
        jdbc.update("""
                insert into action_draft (
                    tenant_id, action_id, insight_id, action_type, title, body, rationale, status)
                values (?, ?, ?, 'ticket', ?, 'body', 'rationale', 'draft')
                """, tenantId, actionId, insightId, "title for " + tenantId);
    }
}
