package com.moveinsync.pulse.agent;

import java.util.List;
import java.util.Optional;
import java.util.function.Supplier;

import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.agent.dto.TraceResponse;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

/** HTTP client for the agent's insight endpoints, typed against contracts/insight.schema.json.
 * Every call gets one retry before the failure is surfaced to the caller. */
@Component
public class InsightAgentClient {

    private static final Logger log = LoggerFactory.getLogger(InsightAgentClient.class);

    private final RestClient restClient;

    public InsightAgentClient(RestClient agentRestClient) {
        this.restClient = agentRestClient;
    }

    public List<InsightPacket> listInsights() {
        InsightPacket[] body = withRetry(() -> restClient.get().uri("/insights").retrieve().body(InsightPacket[].class));
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
