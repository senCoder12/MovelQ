package com.moveinsync.pulse.agent;

import java.util.List;
import java.util.Optional;
import java.util.function.Supplier;

import com.moveinsync.pulse.action.dto.AgentActionDraftRequest;
import com.moveinsync.pulse.action.dto.AgentActionDraftResponse;
import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.agent.dto.TraceResponse;
import com.moveinsync.pulse.report.LeadershipNarrativeRequest;
import com.moveinsync.pulse.report.LeadershipNarrativeResponse;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

/** HTTP client for the agent's insight endpoints, typed against contracts/insight.schema.json
 * (plus the leadership-narrative endpoint, which isn't part of that schema but is served by
 * the same agent process). Every call gets one retry before the failure is surfaced to the caller. */
@Component
public class InsightAgentClient {

    private static final Logger log = LoggerFactory.getLogger(InsightAgentClient.class);

    private final RestClient restClient;

    public InsightAgentClient(RestClient agentRestClient) {
        this.restClient = agentRestClient;
    }

    /** Tenants the agent can detect for, read from the warehouse. Lets the refresh job
     * cover every tenant without a hardcoded list going stale. */
    public List<String> listTenants() {
        String[] body = withRetry(() -> restClient.get().uri("/tenants").retrieve().body(String[].class));
        return body == null ? List.of() : List.of(body);
    }

    /** Runs detection for one tenant. This is a warehouse scan, not a lookup -- seconds,
     * not milliseconds -- which is why it is called by the sync job and never on the path
     * of a user request. */
    public List<InsightPacket> listInsights(String tenantId) {
        InsightPacket[] body = withRetry(() -> restClient.get()
                .uri(builder -> builder.path("/insights").queryParam("tenant_id", tenantId).build())
                .retrieve()
                .body(InsightPacket[].class));
        return body == null ? List.of() : List.of(body);
    }

    public Optional<InsightPacket> getInsight(String insightId) {
        try {
            return Optional.ofNullable(
                    withRetry(() -> restClient.get().uri("/insights/{id}", insightId).retrieve().body(InsightPacket.class)));
        } catch (HttpClientErrorException.NotFound ex) {
            return Optional.empty();
        }
    }

    public Optional<TraceResponse> getTrace(String insightId) {
        try {
            return Optional.ofNullable(
                    withRetry(() -> restClient.get().uri("/insights/{id}/trace", insightId).retrieve().body(TraceResponse.class)));
        } catch (HttpClientErrorException.NotFound ex) {
            return Optional.empty();
        }
    }

    public LeadershipNarrativeResponse getLeadershipNarrative(LeadershipNarrativeRequest request) {
        return withRetry(() -> restClient.post()
                .uri("/internal/leadership-narrative")
                .body(request)
                .retrieve()
                .body(LeadershipNarrativeResponse.class));
    }

    /** A 400 (the agent rejecting an inapplicable action type) is not
     * retried and propagates as-is -- ActionDraftService maps it to a 400
     * for the caller instead of the generic BAD_GATEWAY other failures get. */
    public AgentActionDraftResponse draftAction(InsightPacket insight, String type) {
        AgentActionDraftRequest request = new AgentActionDraftRequest(insight, type);
        try {
            return restClient.post()
                    .uri("/internal/draft-action")
                    .body(request)
                    .retrieve()
                    .body(AgentActionDraftResponse.class);
        } catch (HttpClientErrorException.BadRequest ex) {
            throw ex;
        } catch (RestClientException ex) {
            log.warn("Agent call failed, retrying once: {}", ex.getMessage());
            return restClient.post()
                    .uri("/internal/draft-action")
                    .body(request)
                    .retrieve()
                    .body(AgentActionDraftResponse.class);
        }
    }

    /** Retries a call exactly once on any non-404 RestClientException (timeout, connection
     * refused, 5xx, ...). 404s are not retried -- they're handled by the caller. */
    private static <T> T withRetry(Supplier<T> call) {
        try {
            return call.get();
        } catch (HttpClientErrorException.NotFound ex) {
            throw ex;
        } catch (RestClientException ex) {
            log.warn("Agent call failed, retrying once: {}", ex.getMessage());
            return call.get();
        }
    }
}
