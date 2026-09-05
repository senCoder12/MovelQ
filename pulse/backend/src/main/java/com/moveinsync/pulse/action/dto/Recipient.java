package com.moveinsync.pulse.action.dto;

/** Who an action's draft is addressed to. Not a person -- a role plus a
 * display name (a vendor, "Platform team", "Finance team"), since this
 * prototype never actually sends anything to them. */
public record Recipient(String role, String name) {
}
