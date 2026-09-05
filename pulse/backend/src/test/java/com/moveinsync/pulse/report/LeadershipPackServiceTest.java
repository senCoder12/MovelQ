package com.moveinsync.pulse.report;

import java.util.List;

import com.moveinsync.pulse.agent.InsightAgentClient;
import com.moveinsync.pulse.agent.dto.DataQuality;
import com.moveinsync.pulse.agent.dto.Impact;
import com.moveinsync.pulse.agent.dto.InsightEntity;
import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.agent.dto.Metric;
import com.moveinsync.pulse.agent.dto.Narrative;
import com.moveinsync.pulse.report.LeadershipNarrativeResponse.FindingNarrative;
import com.moveinsync.pulse.web.TenantContext;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class LeadershipPackServiceTest {

    private static InsightPacket insight(String id, int severity, String metricId, double metricValue, int n,
            Integer affectedTrips) {
        return new InsightPacket(
                id,
                new Metric(metricId, metricId, metricValue, "%", n, "trailing_30d"),
                new InsightEntity("fleet", "ALL", "Fleet-wide"),
                List.of(),
                List.of(),
                List.of(),
                List.of(),
                new Impact(affectedTrips, null, null),
                new DataQuality(0.0, "high"),
                severity,
                List.of(),
                new Narrative(id + " headline", "", List.of()));
    }

    private static final class FakeAgentClient extends InsightAgentClient {
        private final List<InsightPacket> insights;
        private final LeadershipNarrativeResponse narrativeResponse;

        FakeAgentClient(List<InsightPacket> insights, LeadershipNarrativeResponse narrativeResponse) {
            super(null);
            this.insights = insights;
            this.narrativeResponse = narrativeResponse;
        }

        @Override
        public List<InsightPacket> listInsights() {
            return insights;
        }

        @Override
        public LeadershipNarrativeResponse getLeadershipNarrative(LeadershipNarrativeRequest request) {
            return narrativeResponse;
        }
    }

    @Test
    void assemblesTilesFindingsAndFooterFromInsights() {
        List<InsightPacket> insights = List.of(
                insight("ins_001", 92, "delay_reconciliation_gap", 54.5, 215885, 117605),
                insight("ins_002", 71, "escort_coverage_night_female", 60.8, 81174, 31838),
                insight("ins_003", 58, "ev_contract_mismatch_rate", 8.11, 25351, 2056));

        LeadershipNarrativeResponse narrative = new LeadershipNarrativeResponse(
                "Reported delay data is unreliable across half the fleet",
                "Summary sentence.",
                List.of(
                        new FindingNarrative("ins_001", "body one", "Audit the scheduling path."),
                        new FindingNarrative("ins_002", "body two", "Close the coverage gap."),
                        new FindingNarrative("ins_003", "body three", "Reconcile fuel type at billing.")));

        // InsightSource stands in for Postgres; the agent still supplies the prose.
        LeadershipPackService service = new LeadershipPackService(
                () -> insights, new FakeAgentClient(insights, narrative), new TenantContext());

        LeadershipPack pack = service.assemble("2026-07");

        assertThat(pack.period()).isEqualTo("July 2026");
        assertThat(pack.headline()).isEqualTo(narrative.headline());
        assertThat(pack.scope().tripCount()).isEqualTo(215885);
        assertThat(pack.scope().sites()).containsExactly("All sites");
        assertThat(pack.scope().dateRange().from()).isEqualTo("2026-07-01");
        assertThat(pack.scope().dateRange().to()).isEqualTo("2026-07-31");

        assertThat(pack.tiles()).extracting(LeadershipPack.Tile::label, LeadershipPack.Tile::value)
                .containsExactly(
                        org.assertj.core.groups.Tuple.tuple("Trips analysed", "215,885"),
                        org.assertj.core.groups.Tuple.tuple("Delay data reliable", "45.5%"),
                        org.assertj.core.groups.Tuple.tuple("Night escort coverage", "60.8%"),
                        org.assertj.core.groups.Tuple.tuple("EV contract match", "91.9%"));

        assertThat(pack.findings()).hasSize(3);
        assertThat(pack.findings().get(0).severity()).isEqualTo(92);
        assertThat(pack.findings().get(0).insightId()).isEqualTo("ins_001");
        assertThat(pack.findings().get(0).body()).isEqualTo("body one");
        assertThat(pack.findings().get(0).recommendation()).isEqualTo("Audit the scheduling path.");
        assertThat(pack.findings().get(2).severity()).isEqualTo(58);

        assertThat(pack.footer().computedFromTrips()).isEqualTo(215885);
        assertThat(pack.footer().excludedTrips()).isEqualTo(0);
        assertThat(pack.footer().excludedPct()).isEqualTo(0.0);
        assertThat(pack.footer().exclusionReasons()).contains("Alert/event correlation data unavailable for this period");
    }
}
