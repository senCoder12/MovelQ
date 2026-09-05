// Presentation layer for InsightPacket.
//
// The packet is the contract (contracts/insight.schema.json) and says nothing
// about how an insight should read on screen: it has a metric id, not a
// headline label; a severity int, not a tone. Everything in this file is that
// missing editorial layer, kept out of the components so the card and the
// summary tiles agree on what an insight is called and which colour it carries.
//
// SHAPE_BY_METRIC is keyed on the metric ids the agent ships today. An unknown
// metric id is not an error -- it falls back to the metric's own name and a
// tone derived from severity, so a new detector renders correctly the day it
// lands, just without a hand-written label.

import {
  formatCompact,
  formatCompactInr,
  formatCount,
  formatMinutes,
  formatPct,
} from './format';
import { Attribution, InsightPacket, Reference } from './insight.model';

export type Tone = 'danger' | 'warn' | 'ok';

/** The three summary themes across the top of the brief. */
export type Domain = 'financial' | 'operational' | 'safety';

interface MetricShape {
  /** Uppercase category label on the card, e.g. "TRIP DELAY MASKING". */
  category: string;
  /** One line, table width: what the detector found, in a single clause. */
  summary: string;
  /** Which summary tile this insight rolls up into. */
  domain: Domain;
  /** Tile heading, e.g. "Financial exposure". */
  domainLabel: string;
  /** Short badge on the tile, e.g. "High Risk". */
  domainBadge: string;
  icon: string;
  /** Wording for the tile's big number, e.g. "Monthly risk". */
  valueLabel: string;
  /** One line under the tile's number. */
  blurb: string;
  /** Which field the tile's big number reads. */
  tileKind: TileKind;
}

/** 'cost' = monthly rupees, 'trips' = affected trips, 'gap' = the shortfall
 * below 100% for a metric that measures coverage rather than failure. */
export type TileKind = 'cost' | 'trips' | 'gap';

const SHAPE_BY_METRIC: Record<string, MetricShape> = {
  delay_reconciliation_gap: {
    category: 'Trip delay masking',
    summary: 'Discrepancy between computed arrival time and vendor-reported delay',
    domain: 'operational',
    domainLabel: 'Operational reliability',
    domainBadge: 'Critical',
    icon: 'field-time',
    valueLabel: 'Underreported delays',
    blurb: 'Trips late by over ten minutes while reporting zero or negligible delay in vendor logs.',
    tileKind: 'trips',
  },
  escort_coverage_night_female: {
    category: 'Night escort safety deficit',
    summary: 'Female night trips missing the mandatory security escort',
    domain: 'safety',
    domainLabel: 'Safety & compliance',
    domainBadge: 'Mandate gap',
    icon: 'safety-certificate',
    valueLabel: 'Non-compliance',
    blurb: 'Female night trips missing mandatory security escorts, against a full-coverage mandate.',
    tileKind: 'gap',
  },
  ev_contract_mismatch_rate: {
    category: 'EV contract billing mismatch',
    summary: 'EV contract rates billed on trips that ran on petrol or diesel',
    domain: 'financial',
    domainLabel: 'Financial exposure',
    domainBadge: 'High risk',
    icon: 'thunderbolt',
    valueLabel: 'Monthly risk',
    blurb: 'Billing exposure from trips charged on EV contract terms that ran on other fuel.',
    tileKind: 'cost',
  },
};

const FALLBACK_ICON = 'alert';

export function shapeOf(insight: InsightPacket): MetricShape {
  const known = SHAPE_BY_METRIC[insight.metric.id];
  if (known) {
    return known;
  }
  return {
    category: insight.metric.name,
    summary: insight.narrative.headline,
    domain: insight.impact.cost_inr_month !== undefined ? 'financial' : 'operational',
    domainLabel: insight.metric.name,
    domainBadge: severityLabel(insight.severity),
    icon: FALLBACK_ICON,
    valueLabel: insight.metric.name,
    blurb: insight.narrative.body,
    tileKind: insight.impact.cost_inr_month !== undefined ? 'cost' : 'trips',
  };
}

export function toneOf(severity: number): Tone {
  if (severity >= 80) {
    return 'danger';
  }
  if (severity >= 50) {
    return 'warn';
  }
  return 'ok';
}

export function severityLabel(severity: number): string {
  if (severity >= 80) {
    return 'High severity';
  }
  if (severity >= 50) {
    return 'Medium severity';
  }
  return 'Low severity';
}

// --- Card presentation -----------------------------------------------------

/** Uppercase tag on the card eyebrow. The domain, not the metric: the reader
 * sorts by "is this ops or money" before they read the headline. */
const DOMAIN_TAG: Record<Domain, string> = {
  financial: 'Finance',
  operational: 'Operations',
  safety: 'Safety',
};

export function domainTag(insight: InsightPacket): string {
  return DOMAIN_TAG[shapeOf(insight).domain];
}

const WINDOW_UNIT: Record<string, string> = { h: 'hours', d: 'days', w: 'weeks', m: 'months' };

/** "trailing_30d" -> "Last 30 days". An unrecognised window passes through as
 * written rather than being guessed at. */
export function windowLabel(window: string): string {
  const match = /^trailing_(\d+)([hdwm])$/.exec(window);
  if (!match) {
    return window;
  }
  return `Last ${match[1]} ${WINDOW_UNIT[match[2]]}`;
}

/** The number in the card's right rail: the single figure the reader escalates
 * on. Money first, then time, then volume -- `covers` names the fact tile the
 * rail has already said, so the tile row can drop it instead of repeating it. */
export interface ExposureStat {
  label: string;
  value: string;
  covers: TileKey | null;
}

export function exposureStat(insight: InsightPacket): ExposureStat {
  const { impact, metric } = insight;
  if (impact.cost_inr_month !== undefined) {
    return { label: 'SLA exposure', value: formatCompactInr(impact.cost_inr_month), covers: null };
  }
  if (impact.late_minutes_total !== undefined) {
    return { label: 'Late minutes', value: formatCompact(impact.late_minutes_total), covers: null };
  }
  if (impact.affected_trips !== undefined) {
    return { label: 'Affected trips', value: formatCount(impact.affected_trips), covers: 'volume' };
  }
  return { label: metric.name, value: `${metric.value}${metric.unit}`, covers: null };
}

/** One bordered fact box on the card: a micro-label and a single line of value,
 * coloured span by span so "1.4m vs 9.9m avg" reads as one sentence. */
export type TileKey = 'volume' | 'comparison' | 'culprit' | 'control';

export type SegmentTone = Tone | 'neutral' | 'accent';

export interface TileSegment {
  text: string;
  tone?: SegmentTone;
  /** Machine value (vendor id, shift code, control name) -> monospace. */
  mono?: boolean;
}

export interface FactTile {
  key: TileKey;
  label: string;
  segments: TileSegment[];
  /** The detail the one-line tile had to drop, surfaced on hover. */
  hint?: string;
}

const MAX_TILES = 3;

/**
 * Up to three fact boxes, in priority order, skipping whatever the right rail
 * already shows. A packet that carries fewer facts renders fewer boxes rather
 * than padding the row with blanks.
 */
export function factTiles(insight: InsightPacket, covered: TileKey | null): FactTile[] {
  return [volumeTile(insight), comparisonTile(insight), culpritTile(insight), controlTile(insight)]
    .filter(isTile)
    .filter((tile) => tile.key !== covered)
    .slice(0, MAX_TILES);
}

function volumeTile(insight: InsightPacket): FactTile | null {
  const trips = insight.impact.affected_trips;
  if (trips === undefined) {
    return null;
  }
  return {
    key: 'volume',
    label: 'Impact volume',
    segments: [
      { text: `${formatCount(trips)} trips` },
      { text: `(${formatPct(insight.metric.value)})`, tone: 'danger' },
    ],
    hint: `${formatCount(trips)} of ${formatCount(insight.metric.n)} trips scanned`,
  };
}

function comparisonTile(insight: InsightPacket): FactTile | null {
  const pair = adjacentPair(insight.references);
  if (pair) {
    // The lower figure is what was reported, the higher what actually happened:
    // the gap between them is the finding, so they carry opposite tones.
    const [low, high] = pair[0].value <= pair[1].value ? pair : [pair[1], pair[0]];
    return {
      key: 'comparison',
      label: 'Reported vs actual',
      segments: [
        { text: compactReference(low), tone: 'ok' },
        { text: 'vs', tone: 'neutral' },
        { text: `${compactReference(high)} avg`, tone: 'danger' },
      ],
      hint: `${low.label}: ${compactReference(low)} — ${high.label}: ${compactReference(high)}`,
    };
  }

  const [only] = insight.references.filter(isNumericReference);
  if (only) {
    // One reference and no pair: compare the metric against it. No tone here --
    // the packet does not say which direction is good for this metric.
    return {
      key: 'comparison',
      label: 'Measured vs reference',
      segments: [
        { text: `${insight.metric.value}${insight.metric.unit}` },
        { text: 'vs', tone: 'neutral' },
        { text: `${compactReference(only)} ${only.type}`, tone: 'neutral' },
      ],
      hint: only.label,
    };
  }

  const text = insight.references[0];
  if (text) {
    return {
      key: 'comparison',
      label: 'Expected value',
      segments: [{ text: String(text.value), mono: true }],
      hint: text.label,
    };
  }
  return null;
}

function culpritTile(insight: InsightPacket): FactTile | null {
  const top = topCulprit(insight.attribution);
  if (!top) {
    return null;
  }
  return {
    key: 'culprit',
    label: 'Top concentrated culprit',
    segments: [{ text: top.value, tone: 'accent', mono: top.dim !== 'vendor_id' }],
    hint: `${top.dim} ${top.value} — ${formatPct(top.contribution_pct)} of the gap, n=${formatCount(top.n)}`,
  };
}

function controlTile(insight: InsightPacket): FactTile | null {
  const [control] = insight.controls;
  if (!control) {
    return null;
  }
  return {
    key: 'control',
    label: 'Control survival',
    segments: [
      { text: `${control.control} ${control.gap_pp > 0 ? '+' : ''}${control.gap_pp}pp`, mono: true },
      { text: control.survives ? 'survives' : 'explained away', tone: control.survives ? 'danger' : 'ok' },
    ],
    hint: `Gap remaining after controlling for ${control.control}`,
  };
}

/**
 * A named vendor reads as a culprit where a shift code reads as a symptom, so a
 * vendor wins over a higher-contributing dimension when the packet has both.
 */
function topCulprit(attribution: Attribution[]): Attribution | null {
  if (attribution.length === 0) {
    return null;
  }
  const byShare = [...attribution].sort((a, b) => b.contribution_pct - a.contribution_pct);
  return byShare.find((item) => item.dim === 'vendor_id') ?? byShare[0];
}

interface NumericReference extends Reference {
  value: number;
}

function isNumericReference(reference: Reference): reference is NumericReference {
  return typeof reference.value === 'number';
}

/**
 * The schema has no field pairing two references, so adjacency is the only
 * signal available: a detector that emits a reported/actual pair emits them
 * consecutively and in the same unit.
 */
function adjacentPair(references: Reference[]): [NumericReference, NumericReference] | null {
  for (let i = 0; i + 1 < references.length; i += 1) {
    const left = references[i];
    const right = references[i + 1];
    if (isNumericReference(left) && isNumericReference(right) && left.unit === right.unit) {
      return [left, right];
    }
  }
  return null;
}

/** Reference value at tile width: "1.4m", not "1.38 min". */
function compactReference(reference: NumericReference): string {
  switch (reference.unit) {
    case 'minutes':
      return formatMinutes(reference.value);
    case 'percent':
      return formatPct(reference.value);
    case 'inr':
      return formatCompactInr(reference.value);
    default:
      return formatCompact(reference.value);
  }
}

function isTile(tile: FactTile | null): tile is FactTile {
  return tile !== null;
}

/** "58% concentrated in X & Y" -- the one-line version used by summary tiles. */
export function topContributors(attribution: Attribution[]): string | null {
  if (attribution.length === 0) {
    return null;
  }
  const top = [...attribution].sort((a, b) => b.contribution_pct - a.contribution_pct)[0];
  return `${formatPct(top.contribution_pct)} concentrated in ${top.value}`;
}

// --- Summary tiles ---------------------------------------------------------

/** One of the headline tiles across the top of the brief. */
export interface SummaryTile {
  insightId: string;
  label: string;
  badge: string;
  tone: Tone;
  value: string;
  valueLabel: string;
  blurb: string;
  footnote: string;
}

const DOMAIN_ORDER: Domain[] = ['financial', 'operational', 'safety'];

/**
 * One tile per domain, taking the most severe insight in that domain. Domains
 * with no insight are dropped rather than rendered empty, so a tenant with only
 * billing findings gets one tile, not three with two blank.
 */
export function summaryTiles(insights: InsightPacket[]): SummaryTile[] {
  const byDomain = new Map<Domain, InsightPacket>();
  for (const insight of insights) {
    const { domain } = shapeOf(insight);
    const held = byDomain.get(domain);
    if (!held || insight.severity > held.severity) {
      byDomain.set(domain, insight);
    }
  }

  return DOMAIN_ORDER.flatMap((domain) => {
    const insight = byDomain.get(domain);
    if (!insight) {
      return [];
    }
    const shape = shapeOf(insight);
    return [
      {
        insightId: insight.insight_id,
        label: shape.domainLabel,
        badge: shape.domainBadge,
        tone: toneOf(insight.severity),
        value: tileValue(insight, shape.tileKind),
        valueLabel: shape.valueLabel,
        blurb: shape.blurb,
        footnote: tileFootnote(insight),
      },
    ];
  });
}

function tileValue(insight: InsightPacket, kind: TileKind): string {
  const { impact, metric } = insight;
  switch (kind) {
    case 'cost':
      return impact.cost_inr_month !== undefined ? formatCompactInr(impact.cost_inr_month) : '—';
    case 'gap':
      // The metric measures coverage, so the finding is the shortfall below 100%.
      return formatPct(100 - metric.value);
    case 'trips':
    default:
      return impact.affected_trips !== undefined ? formatCompact(impact.affected_trips) : '—';
  }
}

function tileFootnote(insight: InsightPacket): string {
  const contributors = topContributors(insight.attribution);
  if (contributors) {
    return contributors;
  }
  if (insight.impact.affected_trips !== undefined) {
    return `${formatCount(insight.impact.affected_trips)} affected trips this period`;
  }
  return `${formatPct(insight.data_quality.excluded_pct)} of rows excluded`;
}
