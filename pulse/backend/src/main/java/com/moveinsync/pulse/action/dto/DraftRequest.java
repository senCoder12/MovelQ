package com.moveinsync.pulse.action.dto;

import jakarta.validation.constraints.NotBlank;

/** Body of POST /api/insights/{id}/actions: which action type to draft.
 * Applicability is re-checked by the agent (app/actions/drafters.py), not
 * trusted from the caller -- an inapplicable type comes back as a 400. */
public record DraftRequest(@NotBlank String type) {
}
