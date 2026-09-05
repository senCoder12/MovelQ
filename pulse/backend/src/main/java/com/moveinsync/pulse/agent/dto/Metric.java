package com.moveinsync.pulse.agent.dto;

/** Matches contracts/insight.schema.json $defs.metric. */
public record Metric(String id, String name, double value, String unit, int n, String window) {
}
