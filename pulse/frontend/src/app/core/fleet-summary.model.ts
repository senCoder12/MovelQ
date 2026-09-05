// The insights dashboard reads two different things.
//
// Most of it comes off the InsightPacket feed and is derived in
// fleet-summary.ts -- flagged trips, analysed trips, exposure, the category
// split, the vendor ranking. Those are real detector output.
//
// The rest is what this file names: figures the packet contract
// (contracts/insight.schema.json) has no field for at all. A packet describes
// one finding in one window; it carries no day-by-day series, no prior-period
// count, and no review outcome. Rather than fake those inside the component,
// they are pulled through FleetSummarySource, which has exactly one
// implementation today (fixtures) and is meant to gain a second (HTTP) the day
// the endpoint lands.

/** One column of the daily anomaly trend. */
export interface DailyPoint {
  /** ISO date, yyyy-mm-dd. */
  date: string;
  /** Anomalies detected that day. */
  total: number;
  /** Of those, the ones since resolved or verified against telematics. */
  resolved: number;
}

/**
 * Everything on the insights page that the packet feed cannot answer.
 * Deliberately small: anything derivable from InsightPacket belongs in
 * fleet-summary.ts instead, so this shrinks as the contract grows.
 */
export interface FleetSupplement {
  /** Trips flagged in the window before the current one, for the trend delta. */
  priorFlagged: number;
  /** Share of flagged trips closed by review, 0-100. */
  resolutionPct: number;
  /** Rupees of the exposure a vendor is actively contesting. */
  disputedInr: number;
  /** One point per day in the selected period, oldest first. */
  daily: DailyPoint[];
}
