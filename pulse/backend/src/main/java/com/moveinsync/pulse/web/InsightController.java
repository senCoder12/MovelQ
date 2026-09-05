package com.moveinsync.pulse.web;

import java.util.List;
import java.util.Optional;
import java.util.function.Supplier;

import com.moveinsync.pulse.agent.InsightAgentClient;
import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.agent.dto.TraceResponse;
import com.moveinsync.pulse.web.DataQualityResponse.Entry;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

/** Single-insight lookups, trace drill-down, and the data-quality summary. Payloads
 * pass through from the agent as-is (tenant-filtered) -- no detection logic yet. */
@RestController
@RequestMapping("/api")
public class InsightController {

    private final InsightAgentClient agentClient;
    private final TenantScopeFilter tenantScopeFilter;
    private final TenantContext tenantContext;

    public InsightController(InsightAgentClient agentClient, TenantScopeFilter tenantScopeFilter, TenantContext tenantContext) {
        this.agentClient = agentClient;
        this.tenantScopeFilter = tenantScopeFilter;
        this.tenantContext = tenantContext;
    }

    @GetMapping("/insights/{id}")
    public InsightPacket getInsight(@PathVariable String id) {
        InsightPacket insight = fetch(() -> agentClient.getInsight(id)).orElseThrow(InsightController::notFound);
        if (!tenantScopeFilter.matchesTenant(insight, tenantContext.tenantId())) {
            throw notFound();
        }
        return insight;
    }

    @GetMapping("/insights/{id}/trace")
    public TraceResponse getTrace(@PathVariable String id) {
        InsightPacket insight = fetch(() -> agentClient.getInsight(id)).orElseThrow(InsightController::notFound);
        if (!tenantScopeFilter.matchesTenant(insight, tenantContext.tenantId())) {
            throw notFound();
        }
        return fetch(() -> agentClient.getTrace(id)).orElseThrow(InsightController::notFound);
    }

    @GetMapping("/data-quality")
    public DataQualityResponse getDataQuality() {
        List<InsightPacket> insights = tenantScopeFilter.apply(fetchAll(), tenantContext.tenantId());
        List<Entry> entries = insights.stream()
                .map(insight -> new Entry(insight.insightId(), insight.metric().id(), insight.dataQuality()))
                .toList();
        return new DataQualityResponse(entries);
    }

    private List<InsightPacket> fetchAll() {
        try {
            return agentClient.listInsights();
        } catch (RestClientException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "agent unavailable", ex);
        }
    }

    private static <T> Optional<T> fetch(Supplier<Optional<T>> call) {
        try {
            return call.get();
        } catch (RestClientException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "agent unavailable", ex);
        }
    }

    private static ResponseStatusException notFound() {
        return new ResponseStatusException(HttpStatus.NOT_FOUND);
    }
}
