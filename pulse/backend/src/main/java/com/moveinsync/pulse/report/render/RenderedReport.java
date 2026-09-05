package com.moveinsync.pulse.report.render;

/** Output of LeadershipPackRenderer.render() -- rendered exactly once and
 * then stored verbatim on the dispatch row. Nothing downstream re-renders
 * from a LeadershipPack again, which is what keeps a past dispatch immutable
 * even after the underlying insights change. */
public record RenderedReport(String subject, String bodyHtml, String bodyText) {
}
