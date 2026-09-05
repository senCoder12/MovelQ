package com.moveinsync.pulse.agent.dto;

/** Matches contracts/insight.schema.json $defs.entity. Named InsightEntity (not Entity)
 * to stay unambiguous once JPA entities land in com.moveinsync.pulse.insight. */
public record InsightEntity(String dim, String id, String name) {
}
