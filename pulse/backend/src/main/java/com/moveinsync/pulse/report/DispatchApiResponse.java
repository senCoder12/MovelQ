package com.moveinsync.pulse.report;

/** Response of POST /api/reports/leadership/dispatch. `duplicate` is true
 * when ReportDispatchService found an existing dispatch for the same
 * (tenant, period, content_hash) within the last hour and returned it
 * instead of sending again -- `dispatch` is that existing record either
 * way, never a partially-built one, so the frontend can always link
 * straight to it. */
public record DispatchApiResponse(DispatchView dispatch, boolean duplicate) {
}
