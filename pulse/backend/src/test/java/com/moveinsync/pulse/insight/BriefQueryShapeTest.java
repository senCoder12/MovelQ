package com.moveinsync.pulse.insight;

import java.util.List;

import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.tenant.TenantContextHolder;

import jakarta.persistence.EntityManagerFactory;

import org.hibernate.SessionFactory;
import org.hibernate.stat.Statistics;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Pins the shape of the brief query: one statement, however many child rows hang off the
 * insights.
 *
 * <p>This is a latency test, not a style test. Neon is in us-east-2 and the demo runs from
 * India, so every extra statement is another 150-250ms on the wire. An N+1 that nobody would
 * notice on localhost would put the brief well past its budget, and it would show up on
 * stage rather than here.
 *
 * <p>Runs against the same configuration the application uses -- including
 * {@code ddl-auto: validate}, so a mapping that has drifted from the migrations fails here
 * too. Statistics are switched on for this class only.
 */
@SpringBootTest(properties = {
        "spring.jpa.properties.hibernate.generate_statistics=true",
        "spring.jpa.properties.hibernate.session.events.log=false"
})
@Transactional
class BriefQueryShapeTest {

    private static final String TENANT = "catalyst";

    @Autowired
    private InsightQueryService insights;

    @Autowired
    private EntityManagerFactory entityManagerFactory;

    @Autowired
    private JdbcTemplate jdbc;

    @BeforeEach
    void insertInsightsWithChildren() {
        TenantContextHolder.clear();
        insertInsight("shape_1", 90);
        insertInsight("shape_2", 80);
        insertInsight("shape_3", 70);
        for (String insightId : List.of("shape_1", "shape_2", "shape_3")) {
            for (int ordinal = 0; ordinal < 4; ordinal++) {
                jdbc.update("""
                        insert into insight_reference (tenant_id, insight_id, ordinal, ref_type, label, value_num, unit)
                        values (?, ?, ?, 'computed', ?, ?, 'percent')
                        """, TENANT, insightId, ordinal, "reference " + ordinal, 1.0 * ordinal);
            }
            for (int ordinal = 0; ordinal < 3; ordinal++) {
                jdbc.update("""
                        insert into insight_attribution (tenant_id, insight_id, ordinal, dim, value, contribution_pct, n)
                        values (?, ?, ?, 'vendor_id', ?, ?, 100)
                        """, TENANT, insightId, ordinal, "vendor " + ordinal, 10.0 * ordinal);
            }
            for (int ordinal = 0; ordinal < 2; ordinal++) {
                jdbc.update("""
                        insert into insight_control (tenant_id, insight_id, ordinal, control, gap_pp, survives)
                        values (?, ?, ?, ?, 5.0, true)
                        """, TENANT, insightId, ordinal, "control " + ordinal);
            }
        }
    }

    @Test
    @DisplayName("the brief is one statement, and the children still come back whole")
    void briefIssuesASingleStatement() {
        TenantContextHolder.set(TENANT);
        Statistics statistics = entityManagerFactory.unwrap(SessionFactory.class).getStatistics();
        statistics.clear();

        List<InsightPacket> packets = insights.listInsights();

        assertThat(statistics.getPrepareStatementCount())
                .as("brief must not fan out into a query per insight")
                .isEqualTo(1);

        assertThat(packets).extracting(InsightPacket::insightId).contains("shape_1", "shape_2", "shape_3");
        InsightPacket packet = packets.stream()
                .filter(candidate -> candidate.insightId().equals("shape_1"))
                .findFirst()
                .orElseThrow();
        assertThat(packet.references()).hasSize(4);
        assertThat(packet.attribution()).hasSize(3);
        assertThat(packet.controls()).hasSize(2);
        assertThat(packet.references()).extracting(reference -> reference.label())
                .containsExactly("reference 0", "reference 1", "reference 2", "reference 3");
    }

    @Test
    @DisplayName("insights are ordered worst first")
    void briefIsOrderedBySeverityDescending() {
        TenantContextHolder.set(TENANT);

        List<Integer> severities = insights.listInsights().stream().map(InsightPacket::severity).toList();

        assertThat(severities).isSortedAccordingTo((left, right) -> Integer.compare(right, left));
    }

    private void insertInsight(String insightId, int severity) {
        jdbc.update("""
                insert into insight (
                    tenant_id, insight_id, severity,
                    metric_id, metric_name, metric_value, metric_unit, metric_n, metric_window,
                    entity_dim, entity_ref, entity_name,
                    data_quality_excluded_pct, data_quality_confidence,
                    narrative_headline, narrative_body)
                values (?, ?, ?, 'shape_metric', 'Shape metric', 1.0, '%', 1, 'trailing_30d',
                        'fleet', 'ALL', 'Fleet-wide', 0.0, 'high', ?, 'shape fixture')
                """, TENANT, insightId, severity, "headline " + insightId);
    }
}
