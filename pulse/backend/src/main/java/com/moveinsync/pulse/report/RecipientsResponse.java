package com.moveinsync.pulse.report;

import java.util.List;

/** `transport` rides along here (not a separate endpoint) because the send
 * drawer's Step 1 is the first call it makes -- carrying the active
 * transport from the start means the button label in Step 3 never has to
 * be a second round trip or a hardcoded guess. */
public record RecipientsResponse(List<RecipientView> recipients, String transport) {
}
