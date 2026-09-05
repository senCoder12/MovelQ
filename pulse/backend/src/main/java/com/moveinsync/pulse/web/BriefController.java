package com.moveinsync.pulse.web;

import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Set;

import com.moveinsync.pulse.agent.InsightAgentClient;
import com.moveinsync.pulse.agent.dto.InsightPacket;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

/** Persona-scoped insight feed. Passes the agent's /insights payload through, tenant-filtered
 * and sorted by severity desc -- no ranking/detection logic yet. */
@RestController
@RequestMapping("/api")
public class BriefController {

    private static final Set<String> PERSONAS = Set.of("ops", "strategic", "shift");

    private final InsightAgentClient agentClient;
    private final TenantScopeFilter tenantScopeFilter;
    private final TenantContext tenantContext;

    public BriefController(InsightAgentClient agentClient, TenantScopeFilter tenantScopeFilter, TenantContext tenantContext) {
        this.agentClient = agentClient;
        this.tenantScopeFilter = tenantScopeFilter;
        this.tenantContext = tenantContext;
    }

    @GetMapping("/brief")
    public BriefResponse brief(@RequestParam String persona) {
        if (!PERSONAS.contains(persona)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "unknown persona: " + persona);
        }
        List<InsightPacket> insights = tenantScopeFilter.apply(fetchInsights(), tenantContext.tenantId()).stream()
                .sorted(Comparator.comparingInt(InsightPacket::severity).reversed())
                .toList();
        return new BriefResponse(persona, Instant.now(), insights);
    }

    private List<InsightPacket> fetchInsights() {
        try {
            return agentClient.listInsights();
        } catch (RestClientException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "agent unavailable", ex);
        }
    }
}
