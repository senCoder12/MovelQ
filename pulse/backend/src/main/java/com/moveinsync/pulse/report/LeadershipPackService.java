package com.moveinsync.pulse.report;

import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import java.text.NumberFormat;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import com.moveinsync.pulse.agent.InsightAgentClient;
import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.report.LeadershipNarrativeRequest.FindingContext;
import com.moveinsync.pulse.report.LeadershipNarrativeResponse.FindingNarrative;
import com.moveinsync.pulse.report.LeadershipPack.DateRange;
import com.moveinsync.pulse.report.LeadershipPack.Direction;
import com.moveinsync.pulse.report.LeadershipPack.Finding;
import com.moveinsync.pulse.report.LeadershipPack.Footer;
import com.moveinsync.pulse.report.LeadershipPack.Scope;
import com.moveinsync.pulse.report.LeadershipPack.Tile;
import com.moveinsync.pulse.web.TenantContext;
import com.moveinsync.pulse.web.TenantScopeFilter;

import org.springframework.stereotype.Service;

/** Assembles the leadership pack: Java gathers every structured field (scope,
 * tiles, per-finding metrics, footer) from the agent's insight feed, then
 * hands that structure to the agent's /internal/leadership-narrative endpoint
 * for the prose (headline, summary, per-finding body/recommendation). No LLM
 * call happens here -- this class only ever asks for numbers it already has
 * grounded in a fetched InsightPacket. */
@Service
public class LeadershipPackService {

    private static final int MAX_FINDINGS = 3;
    private static final DateTimeFormatter PERIOD_DISPLAY = DateTimeFormatter.ofPattern("MMMM yyyy", Locale.ENGLISH);
    private static final NumberFormat TRIP_COUNT_FORMAT = NumberFormat.getIntegerInstance(Locale.US);

    private final InsightAgentClient agentClient;
    private final TenantScopeFilter tenantScopeFilter;
    private final TenantContext tenantContext;

    public LeadershipPackService(InsightAgentClient agentClient, TenantScopeFilter tenantScopeFilter, TenantContext tenantContext) {
        this.agentClient = agentClient;
        this.tenantScopeFilter = tenantScopeFilter;
        this.tenantContext = tenantContext;
    }

    public LeadershipPack assemble(String period) {
        YearMonth yearMonth = YearMonth.parse(period);
        String periodDisplay = yearMonth.format(PERIOD_DISPLAY);

        List<InsightPacket> insights = tenantScopeFilter.apply(agentClient.listInsights(), tenantContext.tenantId());
        List<InsightPacket> topFindings = insights.stream()
                .sorted(Comparator.comparingInt(InsightPacket::severity).reversed())
                .limit(MAX_FINDINGS)
                .toList();

        int tripCount = insights.stream().mapToInt(insight -> insight.metric().n()).max().orElse(0);

        Scope scope = new Scope(tenantContext.tenantId(), sitesOf(insights), tripCount,
                new DateRange(yearMonth.atDay(1).toString(), yearMonth.atEndOfMonth().toString()));
        List<Tile> tiles = buildTiles(insights, tripCount, periodDisplay);
        Footer footer = buildFooter(insights, tripCount);

        List<Finding> findingShells = topFindings.stream()
                .map(insight -> new Finding(insight.narrative().headline(), insight.severity(), null, null, insight.insightId()))
                .toList();
        List<FindingContext> findingContexts = topFindings.stream().map(LeadershipPackService::toFindingContext).toList();

        LeadershipNarrativeRequest request = new LeadershipNarrativeRequest(periodDisplay, scope, tiles, findingContexts, footer);
        LeadershipNarrativeResponse narrative = agentClient.getLeadershipNarrative(request);

        List<Finding> findings = mergeNarrative(findingShells, narrative);
        return new LeadershipPack(periodDisplay, scope, narrative.headline(), narrative.summary(), tiles, findings, footer);
    }

    private static List<String> sitesOf(List<InsightPacket> insights) {
        List<String> sites = insights.stream()
                .filter(insight -> "site".equals(insight.entity().dim()))
                .map(insight -> insight.entity().name())
                .distinct()
                .toList();
        return sites.isEmpty() ? List.of("All sites") : sites;
    }

    /** Every derived tile represents an insight the pipeline flagged as a gap, so its
     * direction is BAD by construction; only the plain trip count is NEUTRAL. Capped
     * at 4 -- trip count plus one tile per known metric id, matching the pack's max. */
    private static List<Tile> buildTiles(List<InsightPacket> insights, int tripCount, String periodDisplay) {
        List<Tile> tiles = new ArrayList<>();
        tiles.add(new Tile("Trips analysed", TRIP_COUNT_FORMAT.format(tripCount), periodDisplay, Direction.NEUTRAL));

        Map<String, InsightPacket> byMetricId = new LinkedHashMap<>();
        for (InsightPacket insight : insights) {
            byMetricId.putIfAbsent(insight.metric().id(), insight);
        }

        InsightPacket delayGap = byMetricId.get("delay_reconciliation_gap");
        if (delayGap != null) {
            tiles.add(new Tile("Delay data reliable", formatPct(100 - delayGap.metric().value()), "of trips", Direction.BAD));
        }
        InsightPacket escort = byMetricId.get("escort_coverage_night_female");
        if (escort != null) {
            tiles.add(new Tile("Night escort coverage", formatPct(escort.metric().value()), "female, 20:00-06:00", Direction.BAD));
        }
        InsightPacket evMismatch = byMetricId.get("ev_contract_mismatch_rate");
        if (evMismatch != null) {
            Integer mismatched = evMismatch.impact() == null ? null : evMismatch.impact().affectedTrips();
            String reference = mismatched == null ? "mismatched" : TRIP_COUNT_FORMAT.format(mismatched) + " mismatched";
            tiles.add(new Tile("EV contract match", formatPct(100 - evMismatch.metric().value()), reference, Direction.BAD));
        }
        return tiles.size() > 4 ? tiles.subList(0, 4) : tiles;
    }

    private static Footer buildFooter(List<InsightPacket> insights, int tripCount) {
        double excludedPct = insights.stream()
                .mapToDouble(insight -> insight.dataQuality().excludedPct())
                .average()
                .orElse(0.0);
        int excludedTrips = (int) Math.round(tripCount * (excludedPct / 100));

        List<String> reasons = new ArrayList<>();
        boolean anyAlertsUnavailable = insights.stream().anyMatch(insight -> insight.coincidentEvents().isEmpty());
        if (anyAlertsUnavailable) {
            reasons.add("Alert/event correlation data unavailable for this period");
        }
        return new Footer(tripCount, excludedTrips, roundTo1Decimal(excludedPct), reasons);
    }

    private static FindingContext toFindingContext(InsightPacket insight) {
        return new FindingContext(
                insight.insightId(),
                insight.severity(),
                insight.narrative().headline(),
                insight.metric(),
                insight.impact(),
                insight.attribution(),
                insight.controls(),
                insight.references());
    }

    private static List<Finding> mergeNarrative(List<Finding> shells, LeadershipNarrativeResponse narrative) {
        Map<String, FindingNarrative> byInsightId = new LinkedHashMap<>();
        for (FindingNarrative finding : narrative.findings()) {
            byInsightId.put(finding.insightId(), finding);
        }
        List<Finding> merged = new ArrayList<>();
        for (Finding shell : shells) {
            FindingNarrative prose = byInsightId.get(shell.insightId());
            String body = prose == null ? "" : prose.body();
            String recommendation = prose == null ? "" : prose.recommendation();
            merged.add(new Finding(shell.title(), shell.severity(), body, recommendation, shell.insightId()));
        }
        return merged;
    }

    private static String formatPct(double value) {
        return String.format(Locale.US, "%.1f%%", roundTo1Decimal(value));
    }

    private static double roundTo1Decimal(double value) {
        return Math.round(value * 10) / 10.0;
    }
}
