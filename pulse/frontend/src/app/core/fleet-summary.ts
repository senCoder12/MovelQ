// Fleet-level rollups derived from the InsightPacket feed.
//
// Everything here is real detector output reshaped -- no figure in this file is
// invented. What the packets genuinely cannot answer lives behind
// FleetSummarySource instead (fleet-summary.source.ts).

import { Domain, shapeOf } from './insight-presentation';
import { InsightPacket } from './insight.model';

/** Headline counts across the whole feed. */
export interface FleetTotals {
  /** Trips implicated by at least one detector. */
  flagged: number;
  /** Trips the detectors looked at -- the widest denominator in the feed. */
  analysed: number;
  /** Monthly rupee exposure the packets put a number on. */
  exposureInr: number;
  /** Of that exposure, the part carried by findings below high confidence. */
  unverifiedInr: number;
}

export function fleetTotals(insights: InsightPacket[]): FleetTotals {
  let flagged = 0;
  let analysed = 0;
  let exposureInr = 0;
  let unverifiedInr = 0;

  for (const insight of insights) {
    flagged += insight.impact.affected_trips ?? 0;
    // The denominators overlap (each detector scans its own slice of the same
    // fleet), so they are not additive -- the widest one is the fleet.
    analysed = Math.max(analysed, insight.metric.n);
    const cost = insight.impact.cost_inr_month ?? 0;
    exposureInr += cost;
    if (insight.data_quality.confidence !== 'high') {
      unverifiedInr += cost;
    }
  }
  return { flagged, analysed, exposureInr, unverifiedInr };
}

/** One row of the "top impact by category" panel. */
export interface CategorySlice {
  domain: Domain;
  label: string;
  /** Share of all flagged trips this domain carries, 0-100. */
  sharePct: number;
  trips: number;
  color: string;
}

/** Fixed per domain so the colour means the same thing on every surface. */
const DOMAIN_COLOR: Record<Domain, string> = {
  operational: 'var(--pulse-cat-1)',
  safety: 'var(--pulse-danger)',
  financial: 'var(--pulse-warn)',
};

/**
 * Flagged trips grouped by domain, largest first. Share is of flagged trips,
 * not of the fleet: the panel answers "which domain is most of the problem",
 * so the shares sum to 100 by construction.
 */
export function categorySlices(insights: InsightPacket[]): CategorySlice[] {
  const byDomain = new Map<Domain, CategorySlice>();

  for (const insight of insights) {
    const trips = insight.impact.affected_trips ?? 0;
    if (trips === 0) {
      continue;
    }
    const shape = shapeOf(insight);
    const held = byDomain.get(shape.domain);
    if (held) {
      held.trips += trips;
      continue;
    }
    byDomain.set(shape.domain, {
      domain: shape.domain,
      label: shape.category,
      sharePct: 0,
      trips,
      color: DOMAIN_COLOR[shape.domain],
    });
  }

  const slices = [...byDomain.values()];
  const total = slices.reduce((sum, slice) => sum + slice.trips, 0);
  if (total === 0) {
    return [];
  }
  for (const slice of slices) {
    slice.sharePct = round1((slice.trips / total) * 100);
  }
  return slices.sort((a, b) => b.trips - a.trips);
}

/** One row of the "top discrepant vendors" panel. */
export interface VendorExposure {
  name: string;
  /** Trips attributed to this vendor across every finding that names it. */
  incidents: number;
  /** Share of all vendor-attributed incidents, 0-100. */
  sharePct: number;
  exposureInr: number;
}

/**
 * Vendors ranked by rupee exposure.
 *
 * The packets attribute trips to vendors but never rupees, so the fleet's own
 * exposure is apportioned by each vendor's share of attributed incidents. That
 * keeps the panel bounded: the rows sum to the exposure the headline card
 * shows, instead of pricing every attributed trip at a rate borrowed from the
 * one finding that happens to carry a cost.
 */
export function vendorExposure(insights: InsightPacket[], limit = 3): VendorExposure[] {
  const { exposureInr } = fleetTotals(insights);
  const byVendor = new Map<string, VendorExposure>();

  for (const insight of insights) {
    for (const item of insight.attribution) {
      if (!item.dim.includes('vendor')) {
        continue;
      }
      const held = byVendor.get(item.value);
      if (held) {
        held.incidents += item.n;
        continue;
      }
      byVendor.set(item.value, { name: item.value, incidents: item.n, sharePct: 0, exposureInr: 0 });
    }
  }

  const rows = [...byVendor.values()];
  const total = rows.reduce((sum, row) => sum + row.incidents, 0);
  for (const row of rows) {
    const share = total === 0 ? 0 : row.incidents / total;
    row.sharePct = round1(share * 100);
    row.exposureInr = Math.round(share * exposureInr);
  }
  return rows.sort((a, b) => b.incidents - a.incidents).slice(0, limit);
}

function round1(value: number): number {
  return Math.round(value * 10) / 10;
}
