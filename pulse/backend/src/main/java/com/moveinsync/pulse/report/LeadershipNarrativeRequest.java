package com.moveinsync.pulse.report;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.moveinsync.pulse.agent.dto.Attribution;
import com.moveinsync.pulse.agent.dto.Control;
import com.moveinsync.pulse.agent.dto.Impact;
import com.moveinsync.pulse.agent.dto.Metric;
import com.moveinsync.pulse.agent.dto.Reference;
import com.moveinsync.pulse.report.LeadershipPack.Footer;
import com.moveinsync.pulse.report.LeadershipPack.Scope;
import com.moveinsync.pulse.report.LeadershipPack.Tile;

/** Body posted to the agent's POST /internal/leadership-narrative: every
 * structured field of a LeadershipPack except the prose the agent is being
 * asked to write. Findings carry the raw metric/impact/attribution/control
 * numbers behind each finding (not just title+severity) -- the agent's prose
 * has to cite figures like "58.4% contribution" or "₹2.87M billed", and those
 * numbers live on the source insight, not on the slim LeadershipPack.Finding
 * shape returned to the frontend. */
public record LeadershipNarrativeRequest(
        String period,
        Scope scope,
        List<Tile> tiles,
        List<FindingContext> findings,
        Footer footer) {

    public record FindingContext(
            @JsonProperty("insight_id") String insightId,
            int severity,
            String title,
            Metric metric,
            Impact impact,
            List<Attribution> attribution,
            List<Control> controls,
            List<Reference> references) {
    }
}
