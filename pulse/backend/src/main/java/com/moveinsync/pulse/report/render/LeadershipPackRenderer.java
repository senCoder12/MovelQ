package com.moveinsync.pulse.report.render;

import java.text.NumberFormat;
import java.util.List;
import java.util.Locale;

import com.moveinsync.pulse.report.LeadershipPack;
import com.moveinsync.pulse.report.LeadershipPack.Direction;
import com.moveinsync.pulse.report.LeadershipPack.Finding;
import com.moveinsync.pulse.report.LeadershipPack.Tile;

import org.springframework.stereotype.Component;

/**
 * Renders one LeadershipPack to both bodies a dispatch needs. `body_text` is
 * the same content the on-screen pack shows (mirrors
 * leadership-pack-page.component.ts's toPlainText() line for line, so the
 * clipboard copy and the email's plain-text part never drift). `body_html`
 * is a separate, email-safe document -- table layout, inline styles only,
 * no flexbox/grid, no web fonts, max-width 600px -- built to survive
 * Outlook's stripped-down rendering engine, which historically only trusts
 * table-based HTML with inline styles.
 *
 * Every color below is a hardcoded hex, deliberately NOT read from
 * tokens.scss: email clients (Outlook chief among them) don't evaluate CSS
 * custom properties, so a var(--pulse-*) reference would render as no color
 * at all. These are the light-theme values from tokens.scss, copied by
 * hand -- there is no dark-mode email variant, since most mail clients
 * either ignore prefers-color-scheme entirely or invert colors themselves.
 */
@Component
public class LeadershipPackRenderer {

    private static final NumberFormat COUNT = NumberFormat.getIntegerInstance(Locale.US);

    // --- Hardcoded palette (see class docstring for why) ---
    private static final String C_PAGE_BG = "#f6f7f9";
    private static final String C_CARD_BG = "#ffffff";
    private static final String C_BORDER = "#e2e4ea";
    private static final String C_TEXT_PRIMARY = "#15161a";
    private static final String C_TEXT_SECONDARY = "#52545e";
    private static final String C_TEXT_MUTED = "#85889a";
    private static final String C_GOOD = "#15803d";
    private static final String C_BAD = "#b91c1c";
    private static final String FONT_STACK =
            "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif";

    public RenderedReport render(LeadershipPack pack) {
        String subject = subjectFor(pack);
        return new RenderedReport(subject, renderHtml(pack, subject), renderText(pack));
    }

    private static String subjectFor(LeadershipPack pack) {
        return capitalize(pack.scope().tenant()) + " mobility operations — " + pack.period();
    }

    private static String capitalize(String tenant) {
        if (tenant == null || tenant.isBlank()) {
            return "Pulse";
        }
        return Character.toUpperCase(tenant.charAt(0)) + tenant.substring(1);
    }

    // --- Plain text: identical content to the on-screen pack -----------------

    private static String renderText(LeadershipPack pack) {
        StringBuilder text = new StringBuilder();
        text.append("Mobility operations · ").append(pack.period()).append(" · ")
                .append(String.join(", ", pack.scope().sites())).append('\n');
        text.append('\n').append(pack.headline()).append('\n');
        text.append('\n').append(pack.summary()).append('\n');
        text.append('\n');
        for (Tile tile : pack.tiles()) {
            text.append(tile.label()).append(": ").append(tile.value())
                    .append(" (").append(tile.reference()).append(")\n");
        }
        text.append("\nWhat needs a decision\n");
        for (Finding finding : pack.findings()) {
            text.append('\n').append(finding.title()).append(" [severity ").append(finding.severity()).append("]\n");
            text.append(finding.body()).append('\n');
            text.append("Recommendation: ").append(finding.recommendation()).append('\n');
        }
        text.append("\nComputed from ").append(COUNT.format(pack.footer().computedFromTrips())).append(" trips, ")
                .append(COUNT.format(pack.footer().excludedTrips())).append(" excluded (")
                .append(pack.footer().excludedPct()).append("%).");
        if (!pack.footer().exclusionReasons().isEmpty()) {
            text.append('\n').append(String.join("; ", pack.footer().exclusionReasons()));
        }
        return text.toString();
    }

    // --- Email-safe HTML: table layout, inline styles only -------------------

    private static String renderHtml(LeadershipPack pack, String subject) {
        String sites = String.join(", ", pack.scope().sites());
        StringBuilder html = new StringBuilder();
        html.append("<!doctype html><html><head><meta charset=\"utf-8\">")
                .append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">")
                .append("<title>").append(escape(subject)).append("</title></head>");
        html.append("<body style=\"margin:0;padding:0;background-color:").append(C_PAGE_BG).append(";\">");
        html.append("<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" ")
                .append("style=\"background-color:").append(C_PAGE_BG).append(";\"><tr><td align=\"center\" style=\"padding:24px 16px;\">");
        html.append("<table role=\"presentation\" width=\"600\" cellpadding=\"0\" cellspacing=\"0\" ")
                .append("style=\"max-width:600px;width:100%;background-color:").append(C_CARD_BG)
                .append(";border:1px solid ").append(C_BORDER).append(";border-radius:8px;font-family:")
                .append(FONT_STACK).append(";\">");

        html.append(row(cell(
                "padding:24px 32px 4px 32px;",
                p("margin:0;color:" + C_TEXT_MUTED + ";font-size:12px;text-transform:uppercase;letter-spacing:0.04em;",
                        escape(capitalize(pack.scope().tenant())) + " mobility operations &middot; "
                                + escape(pack.period()) + " &middot; " + escape(sites)))));

        html.append(row(cell("padding:8px 32px 0 32px;",
                "<h1 style=\"margin:0;color:" + C_TEXT_PRIMARY + ";font-size:22px;line-height:1.3;font-weight:600;\">"
                        + escape(pack.headline()) + "</h1>")));

        html.append(row(cell("padding:12px 32px 24px 32px;",
                p("margin:0;color:" + C_TEXT_SECONDARY + ";font-size:14px;line-height:1.6;", escape(pack.summary())))));

        if (!pack.tiles().isEmpty()) {
            html.append(row(cell("padding:0 32px 24px 32px;", renderTiles(pack.tiles()))));
        }

        html.append(row(cell("padding:16px 32px 4px 32px;border-top:1px solid " + C_BORDER + ";",
                p("margin:0;color:" + C_TEXT_MUTED + ";font-size:11px;text-transform:uppercase;letter-spacing:0.04em;",
                        "What needs a decision"))));

        for (Finding finding : pack.findings()) {
            html.append(renderFinding(finding));
        }

        html.append(row(cell("padding:24px 32px;border-top:1px solid " + C_BORDER + ";",
                p("margin:0;color:" + C_TEXT_MUTED + ";font-size:12px;line-height:1.5;", footerLine(pack)))));

        html.append("</table></td></tr></table></body></html>");
        return html.toString();
    }

    private static String renderTiles(List<Tile> tiles) {
        String width = (100 / Math.max(tiles.size(), 1)) + "%";
        StringBuilder inner = new StringBuilder("<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\"><tr>");
        for (Tile tile : tiles) {
            String toneColor = switch (tile.direction()) {
                case GOOD -> C_GOOD;
                case BAD -> C_BAD;
                case NEUTRAL -> C_TEXT_MUTED;
            };
            inner.append("<td width=\"").append(width).append("\" valign=\"top\" style=\"padding:0 8px 0 0;\">")
                    .append("<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" ")
                    .append("style=\"border:1px solid ").append(C_BORDER).append(";border-radius:8px;\"><tr><td style=\"padding:12px;\">")
                    .append(p("margin:0 0 4px 0;color:" + C_TEXT_MUTED + ";font-size:10px;text-transform:uppercase;letter-spacing:0.06em;",
                            escape(tile.label())))
                    .append(p("margin:0 0 4px 0;color:" + C_TEXT_PRIMARY + ";font-size:18px;font-weight:600;", escape(tile.value())))
                    .append(p("margin:0;color:" + toneColor + ";font-size:11px;", escape(tile.reference())))
                    .append("</td></tr></table></td>");
        }
        inner.append("</tr></table>");
        return inner.toString();
    }

    private static String renderFinding(Finding finding) {
        String severityColor = finding.severity() >= 80 ? C_BAD : finding.severity() >= 50 ? "#b45309" : C_GOOD;
        String block = "<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\">"
                + "<tr><td style=\"border-left:3px solid " + severityColor + ";padding:8px 0 8px 12px;\">"
                + "<h3 style=\"margin:0 0 4px 0;color:" + C_TEXT_PRIMARY + ";font-size:15px;font-weight:600;\">"
                + escape(finding.title()) + "</h3>"
                + p("margin:0 0 6px 0;color:" + C_TEXT_SECONDARY + ";font-size:13px;line-height:1.5;", escape(finding.body()))
                + p("margin:0;color:" + C_TEXT_SECONDARY + ";font-size:13px;line-height:1.5;",
                        "<strong>Recommendation:</strong> " + escape(finding.recommendation()))
                + "</td></tr></table>";
        return row(cell("padding:8px 32px;", block));
    }

    private static String footerLine(LeadershipPack pack) {
        StringBuilder line = new StringBuilder();
        line.append("Computed from ").append(COUNT.format(pack.footer().computedFromTrips())).append(" trips &middot; ")
                .append(COUNT.format(pack.footer().excludedTrips())).append(" excluded (")
                .append(pack.footer().excludedPct()).append("%)");
        if (!pack.footer().exclusionReasons().isEmpty()) {
            line.append(" &middot; ").append(escape(String.join("; ", pack.footer().exclusionReasons())));
        }
        return line.toString();
    }

    private static String row(String cellHtml) {
        return "<tr>" + cellHtml + "</tr>";
    }

    private static String cell(String style, String innerHtml) {
        return "<td style=\"" + style + "\">" + innerHtml + "</td>";
    }

    private static String p(String style, String innerHtml) {
        return "<p style=\"" + style + "\">" + innerHtml + "</p>";
    }

    private static String escape(String text) {
        if (text == null) {
            return "";
        }
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace("\"", "&quot;").replace("'", "&#39;");
    }
}
