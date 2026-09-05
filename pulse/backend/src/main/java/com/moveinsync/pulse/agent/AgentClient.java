package com.moveinsync.pulse.agent;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/** HTTP client for the Python agent service. */
@Component
public class AgentClient {

    private static final Logger log = LoggerFactory.getLogger(AgentClient.class);

    private final RestClient restClient;

    public AgentClient(RestClient agentRestClient) {
        this.restClient = agentRestClient;
    }

    /**
     * Calls the agent's /health endpoint. Returns a DOWN payload instead of throwing
     * so the backend stays reachable when the agent is not running.
     */
    public AgentHealth health() {
        try {
            AgentHealth health = restClient.get().uri("/health").retrieve().body(AgentHealth.class);
            return health == null ? down() : health;
        } catch (RuntimeException ex) {
            log.warn("Agent health check failed: {}", ex.getMessage());
            return down();
        }
    }

    private static AgentHealth down() {
        return new AgentHealth("DOWN", "pulse-agent", null);
    }
}
