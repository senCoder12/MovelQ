package com.moveinsync.pulse.alert.dto;

/** A persona's pseudo-recipient for this tenant -- fixed and seeded in code
 * (PersonaRecipients), not a user table, same reasoning as
 * report_recipient's design note but one level lighter: a persona is a
 * routing target, not someone who reviews and edits a draft, so it does
 * not need its own DB-backed roster. */
public record PersonaRecipient(String persona, String name, String email) {
}
