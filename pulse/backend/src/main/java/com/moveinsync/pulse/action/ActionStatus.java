package com.moveinsync.pulse.action;

/** DRAFTED is the only status the agent ever produces. Every other value is
 * written exclusively by ActionDraftService in response to an explicit,
 * per-action human decision -- there is no bulk transition and no timer that
 * moves a draft between these on its own. */
public enum ActionStatus {
    DRAFTED,
    APPROVED,
    REJECTED,
    EDITED_APPROVED
}
