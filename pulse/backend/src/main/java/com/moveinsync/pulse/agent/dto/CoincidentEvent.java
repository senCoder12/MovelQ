package com.moveinsync.pulse.agent.dto;

/** Matches contracts/insight.schema.json $defs.coincident_event. */
public record CoincidentEvent(String type, String date, String note) {
}
