package com.moveinsync.pulse.agent.dto;

/** Matches contracts/insight.schema.json $defs.reference. Value is number|string in the
 * schema; Object keeps both representations without lossy coercion. */
public record Reference(String type, String label, Object value, String unit) {
}
