package com.moveinsync.pulse.alert.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;

/** Body of POST /api/alerts/{id}/mute. Both fields are required -- an
 * alerting system without a mute is one a manager turns off entirely, so
 * the one it has must at least record who asked for silence and for how
 * long, not just that someone clicked a button. */
public record MuteRequest(@NotBlank String reason, @Positive int days) {
}
