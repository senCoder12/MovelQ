package com.moveinsync.pulse.action.dto;

import jakarta.validation.constraints.NotBlank;

/** Body of POST /api/actions/{id}/reject. `reason` is required -- a
 * rejection with no reason is not a decision an auditor can later make
 * sense of. */
public record RejectRequest(@NotBlank String reason) {
}
