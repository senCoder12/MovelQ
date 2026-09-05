package com.moveinsync.pulse.action.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/** What approving this draft actually does. In this prototype "execute"
 * always means writing an ApprovalLog row, never calling a vendor system --
 * `reversible` is true for every action type today because none of them
 * touch anything outside this app. */
public record Preview(@JsonProperty("what_changes") String whatChanges, boolean reversible) {
}
