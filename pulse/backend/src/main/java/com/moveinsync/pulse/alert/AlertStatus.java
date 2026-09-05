package com.moveinsync.pulse.alert;

/** NEW is the only status a scan ever writes. ACKNOWLEDGED and MUTED are
 * explicit human decisions (see AlertService.acknowledge/mute); EXPIRED is
 * reserved for a future retention pass and is not written anywhere yet. */
public enum AlertStatus {
    NEW,
    ACKNOWLEDGED,
    MUTED,
    EXPIRED
}
