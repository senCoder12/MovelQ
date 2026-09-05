package com.moveinsync.pulse.report.render;

import java.util.List;

import com.moveinsync.pulse.report.LeadershipPack;
import com.moveinsync.pulse.report.LeadershipPack.DateRange;
import com.moveinsync.pulse.report.LeadershipPack.Direction;
import com.moveinsync.pulse.report.LeadershipPack.Finding;
import com.moveinsync.pulse.report.LeadershipPack.Footer;
import com.moveinsync.pulse.report.LeadershipPack.Scope;
import com.moveinsync.pulse.report.LeadershipPack.Tile;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class LeadershipPackRendererTest {

    private static LeadershipPack samplePack() {
        return new LeadershipPack(
                "July 2026",
                new Scope("catalyst", List.of("HQ Campus"), 215885, new DateRange("2026-07-01", "2026-07-31")),
                "Reported delay data is unreliable across half the fleet",
                "215,885 trips were analysed; 45.5% have reliable delay data.",
                List.of(
                        new Tile("Trips analysed", "215,885", "July 2026", Direction.NEUTRAL),
                        new Tile("Delay data reliable", "45.5%", "of trips", Direction.BAD)),
                List.of(new Finding("117,605 trips arrived late while reporting zero delay", 92,
                        "58.4% of the contradiction concentrates in the ':16' cluster.",
                        "Audit the ':16' scheduling path.", "ins_001")),
                new Footer(215885, 0, 0.0, List.of("Alert/event correlation data unavailable for this period")));
    }

    private final LeadershipPackRenderer renderer = new LeadershipPackRenderer();

    @Test
    void subjectNamesTheTenantAndThePeriod() {
        RenderedReport rendered = renderer.render(samplePack());
        assertThat(rendered.subject()).isEqualTo("Catalyst mobility operations — July 2026");
    }

    @Test
    void bodyTextMatchesTheOnScreenPackContent() {
        String text = renderer.render(samplePack()).bodyText();
        assertThat(text).contains("Mobility operations · July 2026 · HQ Campus");
        assertThat(text).contains("Reported delay data is unreliable across half the fleet");
        assertThat(text).contains("Trips analysed: 215,885 (July 2026)");
        assertThat(text).contains("What needs a decision");
        assertThat(text).contains("117,605 trips arrived late while reporting zero delay [severity 92]");
        assertThat(text).contains("Recommendation: Audit the ':16' scheduling path.");
        assertThat(text).contains("Computed from 215,885 trips, 0 excluded (0.0%).");
        assertThat(text).contains("Alert/event correlation data unavailable for this period");
    }

    @Test
    void bodyHtmlIsTableBasedWithInlineStylesAndNoModernCss() {
        String html = renderer.render(samplePack()).bodyHtml();
        assertThat(html).contains("<table");
        assertThat(html).contains("max-width:600px");
        assertThat(html).contains(samplePack().headline());
        assertThat(html).doesNotContain("var(--");
        assertThat(html).doesNotContain("display:flex");
        assertThat(html).doesNotContain("display:grid");
        assertThat(html).doesNotContain("<link");
        assertThat(html).doesNotContain("@font-face");
    }

    @Test
    void bodyHtmlEscapesContentFromTheInsight() {
        LeadershipPack pack = new LeadershipPack(
                "July 2026",
                new Scope("catalyst", List.of("HQ"), 100, new DateRange("2026-07-01", "2026-07-31")),
                "A <script>alert(1)</script> headline",
                "summary",
                List.of(),
                List.of(),
                new Footer(100, 0, 0.0, List.of()));
        String html = renderer.render(pack).bodyHtml();
        assertThat(html).doesNotContain("<script>");
        assertThat(html).contains("&lt;script&gt;");
    }

    @Test
    void unknownOrBlankTenantFallsBackRatherThanProducingAnEmptySubject() {
        LeadershipPack pack = new LeadershipPack(
                "July 2026",
                new Scope(null, List.of(), 0, new DateRange("2026-07-01", "2026-07-31")),
                "headline", "summary", List.of(), List.of(), new Footer(0, 0, 0.0, List.of()));
        assertThat(renderer.render(pack).subject()).isEqualTo("Pulse mobility operations — July 2026");
    }
}
