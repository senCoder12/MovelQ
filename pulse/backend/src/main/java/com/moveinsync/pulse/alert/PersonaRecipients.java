package com.moveinsync.pulse.alert;

import com.moveinsync.pulse.alert.dto.PersonaRecipient;

/** Fixed pseudo-recipients per (tenant, persona) -- there is no user table
 * and this alerting feature does not need one either: a persona routes to
 * a role-shaped mailbox, never a named person, so a seeded DB roster like
 * report_recipient's would be one degree more machinery than the thing it
 * is standing in for. Addresses stay on example.com for the same reason
 * every other seeded contact in this app does. */
public final class PersonaRecipients {

    private PersonaRecipients() {
    }

    public static PersonaRecipient forTenant(String tenantId, String persona) {
        String name = switch (persona) {
            case "ops" -> "Ops on-call";
            case "strategic" -> "Strategic lead";
            case "shift" -> "Shift handover";
            default -> persona;
        };
        return new PersonaRecipient(persona, name, persona + "@" + tenantId + ".example.com");
    }
}
