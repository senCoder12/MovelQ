package com.moveinsync.pulse.insight;

import java.util.List;

import com.moveinsync.pulse.agent.dto.InsightPacket;

/** Where assembled insight packets come from. One implementation today
 * ({@link InsightQueryService}, reading Postgres); an interface so callers such as the
 * leadership pack can be tested without a database. */
public interface InsightSource {

    /** Every insight for the tenant in context, worst first. */
    List<InsightPacket> listInsights();
}
