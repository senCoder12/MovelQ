package com.moveinsync.pulse.web;

import java.util.List;

import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.agent.dto.TraceEntry;
import com.moveinsync.pulse.agent.dto.TraceResponse;
import com.moveinsync.pulse.insight.InsightQueryService;
import com.moveinsync.pulse.insight.InsightSyncService;
import com.moveinsync.pulse.web.DataQualityResponse.Entry;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

/** Single-insight lookups, trace drill-down, and the data-quality summary -- all from
 * Postgres. An insight belonging to another tenant is not "forbidden", it is absent: the
 * tenant filter removes it before this code ever sees it, so the answer is a plain 404. */
@RestController
@RequestMapping("/api")
public class InsightController {

    private final InsightQueryService insights;
    private final InsightSyncService sync;
    private final TenantContext tenantContext;

    public InsightController(InsightQueryService insights, InsightSyncService sync, TenantContext tenantContext) {
        this.insights = insights;
        this.sync = sync;
        this.tenantContext = tenantContext;
    }

    /**
     * Re-runs detection for the calling tenant and persists the result.
     *
     * <p>Synchronous, and slow by the standards of everything else here -- it is a warehouse
     * scan followed by a write per insight. That is why it is its own endpoint rather than
     * something the brief does on a cache miss: refreshing is an operator action, reading is
     * not.
     */
    @PostMapping("/insights/refresh")
    public InsightSyncService.SyncResult refresh() {
        return sync.sync(tenantContext.requireTenantId());
    }

    @GetMapping("/insights/{id}")
    public InsightPacket getInsight(@PathVariable String id) {
        return insights.findInsight(id).orElseThrow(InsightController::notFound);
    }

    @GetMapping("/insights/{id}/trace")
    public TraceResponse getTrace(@PathVariable String id) {
        List<TraceEntry> trace = insights.findTrace(id);
        if (trace.isEmpty() && insights.findInsight(id).isEmpty()) {
            throw notFound();
        }
        return new TraceResponse(id, trace);
    }

    @GetMapping("/data-quality")
    public DataQualityResponse getDataQuality() {
        List<Entry> entries = insights.listInsights().stream()
                .map(insight -> new Entry(insight.insightId(), insight.metric().id(), insight.dataQuality()))
                .toList();
        return new DataQualityResponse(entries);
    }

    private static ResponseStatusException notFound() {
        return new ResponseStatusException(HttpStatus.NOT_FOUND);
    }
}
