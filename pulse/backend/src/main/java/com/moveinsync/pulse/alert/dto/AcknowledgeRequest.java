package com.moveinsync.pulse.alert.dto;

/** Body of POST /api/alerts/{id}/acknowledge. `note` is optional. */
public record AcknowledgeRequest(String note) {

    public static AcknowledgeRequest empty() {
        return new AcknowledgeRequest(null);
    }
}
