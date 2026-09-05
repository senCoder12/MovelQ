import { Component, DestroyRef, computed, effect, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { forkJoin } from 'rxjs';

import { BriefService } from '../../core/brief.service';
import {
  CategorySlice,
  VendorExposure,
  categorySlices,
  fleetTotals,
  vendorExposure,
} from '../../core/fleet-summary';
import { DailyPoint, FleetSupplement } from '../../core/fleet-summary.model';
import { FleetSummarySource } from '../../core/fleet-summary.source';
import { formatCompact, formatCompactInr, formatCount, formatPct } from '../../core/format';
import { Domain, shapeOf } from '../../core/insight-presentation';
import { InsightPacket } from '../../core/insight.model';
import { Period, ShellSegment, ShellService } from '../../core/shell.service';
import { TenantService } from '../../core/tenant.service';

/** The top bar's filter. `null` is the unfiltered view; every other key is a
 * domain, so a new domain needs a row here and nothing else. */
const SEGMENTS: readonly (ShellSegment & { domain: Domain | null })[] = [
  { key: 'all', label: 'All', domain: null },
  { key: 'ops', label: 'Ops', domain: 'operational' },
  { key: 'safety', label: 'Safety', domain: 'safety' },
  { key: 'billing', label: 'Billing', domain: 'financial' },
];

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/** Plot box. Rendered with preserveAspectRatio="none", so every stroke inside
 * carries vector-effect="non-scaling-stroke" and anything that must stay round
 * (the peak marker) is positioned in HTML rather than drawn in the SVG. */
const PLOT_W = 720;
const PLOT_H = 200;
/** Gridlines below the top one. Three gives the 0 / a / 2a / 3a scale the axis reads. */
const GRID_STEPS = 3;
const STEP_SIZES = [50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10_000, 20_000, 25_000, 50_000];

type Direction = 'up' | 'down' | 'flat';

interface AxisTick {
  label: string;
  /** Percent across the plot, for absolute placement over the SVG. */
  atPct: number;
  anchor: 'start' | 'middle' | 'end';
}

interface Plot {
  totalLine: string;
  totalArea: string;
  resolvedLine: string;
  resolvedArea: string;
  /** Gridline y positions in viewBox units, top first. */
  grid: number[];
  yTicks: string[];
  xTicks: AxisTick[];
  peak: { leftPct: number; topPct: number };
}

/**
 * The fleet's month at a glance: what moved, what it costs, which domain and
 * which vendors carry it.
 *
 * Everything except the daily series and the two review figures is derived from
 * the same InsightPacket feed the brief renders -- see core/fleet-summary.ts.
 * The rest arrives through FleetSummarySource, which is fixtures today.
 */
@Component({
  selector: 'app-insights-page',
  standalone: true,
  imports: [NzIconModule],
  templateUrl: './insights-page.component.html',
  styleUrl: './insights-page.component.css',
})
export class InsightsPageComponent {
  private readonly briefService = inject(BriefService);
  private readonly router = inject(Router);
  private readonly shell = inject(ShellService);
  private readonly tenants = inject(TenantService);
  private readonly summarySource = inject(FleetSummarySource);

  readonly insights = signal<InsightPacket[]>([]);
  readonly supplement = signal<FleetSupplement | null>(null);
  readonly error = signal<string | null>(null);
  readonly loading = signal(false);

  /** The feed narrowed to the top bar's segment. Every panel below reads this. */
  readonly scoped = computed(() => {
    const domain = SEGMENTS.find((segment) => segment.key === this.shell.activeSegment())?.domain;
    if (!domain) {
      return this.insights();
    }
    return this.insights().filter((insight) => shapeOf(insight).domain === domain);
  });

  readonly totals = computed(() => fleetTotals(this.scoped()));

  /** Unfiltered. The trend card reads this, not `totals`: the prior-window
   * count is fleet-wide, and there is no per-domain baseline to compare a
   * narrowed count against. */
  readonly fleetWide = computed(() => fleetTotals(this.insights()));

  readonly narrowed = computed(() => (this.shell.activeSegment() ?? 'all') !== 'all');

  readonly categories = computed<CategorySlice[]>(() => categorySlices(this.scoped()));
  readonly vendors = computed<VendorExposure[]>(() => vendorExposure(this.scoped()));

  // --- Card 1: incident trend ---

  /** Signed change against the prior window, in percent. */
  readonly deltaPct = computed(() => {
    const prior = this.supplement()?.priorFlagged ?? 0;
    if (prior === 0) {
      return null;
    }
    return Math.round(((this.fleetWide().flagged - prior) / prior) * 1000) / 10;
  });

  readonly direction = computed<Direction>(() => {
    const delta = this.deltaPct();
    if (delta === null || Math.abs(delta) < 1) {
      return 'flat';
    }
    return delta < 0 ? 'down' : 'up';
  });

  readonly trendWord = computed(() =>
    ({ down: 'Improving', up: 'Worsening', flat: 'Holding' })[this.direction()],
  );

  readonly trendBlurb = computed(() =>
    this.narrowed()
      ? 'Fleet-wide, across every domain'
      : ({
          down: 'Consistent week-over-week reduction',
          up: 'Sustained week-over-week increase',
          flat: 'Level against the prior period',
        })[this.direction()],
  );

  readonly trendFoot = computed(
    () => ({ down: 'Trending down', up: 'Trending up', flat: 'Holding flat' })[this.direction()],
  );

  /** Down is fewer flagged trips, so down is the good direction here. */
  readonly trendTone = computed(() =>
    ({ down: 'ok', up: 'danger', flat: 'muted' })[this.direction()],
  );

  /** Signed, at one decimal: "-14.2%". Null when there is no prior window. */
  readonly deltaLabel = computed(() => {
    const delta = this.deltaPct();
    if (delta === null) {
      return null;
    }
    return `${delta > 0 ? '+' : delta < 0 ? '-' : ''}${formatPct(Math.abs(delta))}`;
  });

  readonly priorLabel = computed(() => {
    const prior = this.supplement()?.priorFlagged;
    return prior === undefined ? null : `Prior period: ${formatCompact(prior)}`;
  });

  // --- Card 2: active anomalies ---

  readonly periodBadge = computed(() => monthLabel(this.shell.period()));

  readonly resolutionLabel = computed(() => {
    const pct = this.supplement()?.resolutionPct;
    return pct === undefined ? null : `${formatPct(pct)} cleared`;
  });

  // --- Card 3: financial exposure ---

  readonly disputeLabel = computed(() => {
    const disputed = this.supplement()?.disputedInr;
    return disputed === undefined ? null : `${formatCompactInr(disputed)} in dispute`;
  });

  // --- Chart ---

  readonly plot = computed<Plot | null>(() => {
    const daily = this.supplement()?.daily ?? [];
    return daily.length < 2 ? null : buildPlot(daily);
  });

  // --- Panel footers ---

  readonly primaryCategory = computed<CategorySlice | null>(() => this.categories()[0] ?? null);

  readonly cumulativeExposure = computed(() =>
    this.vendors().reduce((sum, vendor) => sum + vendor.exposureInr, 0),
  );

  constructor() {
    this.shell.setSegments(
      SEGMENTS.map(({ key, label }) => ({ key, label })),
      SEGMENTS[0].key,
    );

    // The pill reports the direction the page's own headline reports -- one
    // reading of the month, not two.
    effect(
      () => {
        const word = { down: 'Fleet normal', up: 'Fleet degrading', flat: 'Fleet steady' }[
          this.direction()
        ];
        const tone = { down: 'ok', up: 'danger', flat: 'warn' }[this.direction()] as
          | 'ok'
          | 'danger'
          | 'warn';
        this.shell.setStatus(this.insights().length === 0 ? null : { label: word, tone });
      },
      { allowSignalWrites: true },
    );

    effect(
      () => {
        this.tenants.tenantId();
        this.shell.period();
        this.shell.refreshTick();
        this.load();
      },
      { allowSignalWrites: true },
    );

    // A view owns its top-bar controls only while it is on screen.
    inject(DestroyRef).onDestroy(() => {
      this.shell.setSegments([]);
      this.shell.setStatus(null);
    });
  }

  openCategory(): void {
    const top = [...this.scoped()].sort((a, b) => b.severity - a.severity)[0];
    if (top) {
      this.shell.requestInsight(top.insight_id);
      this.router.navigateByUrl('/brief');
    }
  }

  openVendors(): void {
    this.router.navigateByUrl('/vendors');
  }

  compact(value: number): string {
    return formatCompact(value);
  }

  compactInr(value: number): string {
    return formatCompactInr(value);
  }

  count(value: number): string {
    return formatCount(value);
  }

  pct(value: number): string {
    return formatPct(value);
  }

  absPct(value: number): string {
    return formatPct(Math.abs(value));
  }

  private load(): void {
    this.loading.set(true);
    this.shell.loading.set(true);
    forkJoin({
      brief: this.briefService.getBrief('ops'),
      supplement: this.summarySource.supplement(this.shell.period()),
    }).subscribe({
      next: ({ brief, supplement }) => {
        this.insights.set(brief.insights);
        this.supplement.set(supplement);
        this.shell.insights.set(brief.insights);
        // Same feed as the brief, so it carries the same agent status line --
        // the top bar should not read "idle" just because this view is open.
        this.shell.agentError.set(null);
        this.shell.agentStatus.set({
          generatedAt: brief.generated_at,
          scannedTrips: brief.insights.reduce((max, insight) => Math.max(max, insight.metric.n), 0),
          signalCount: brief.insights.length,
        });
        this.error.set(null);
        this.loading.set(false);
        this.shell.loading.set(false);
      },
      error: (err) => {
        const message = err?.message ?? 'The backend is unreachable.';
        this.insights.set([]);
        this.supplement.set(null);
        this.shell.agentStatus.set(null);
        this.shell.agentError.set(message);
        this.error.set(message);
        this.loading.set(false);
        this.shell.loading.set(false);
      },
    });
  }
}

function monthLabel(period: Period): string {
  const [year, month] = period.split('-');
  return `${MONTHS[Number(month) - 1] ?? month} ${year}`;
}

/**
 * A round ceiling three gridlines above zero, so the axis reads 0 / a / 2a / 3a
 * with no fractional labels regardless of the day's peak.
 */
function ceilingFor(max: number): number {
  const step = STEP_SIZES.find((size) => size * GRID_STEPS >= max) ?? Math.ceil(max / GRID_STEPS);
  return step * GRID_STEPS;
}

function buildPlot(daily: DailyPoint[]): Plot {
  const ceiling = ceilingFor(Math.max(...daily.map((point) => point.total)));
  const last = daily.length - 1;
  const x = (i: number) => (i / last) * PLOT_W;
  const y = (value: number) => PLOT_H - (value / ceiling) * PLOT_H;

  const line = (pick: (point: DailyPoint) => number) =>
    daily.map((point, i) => `${i === 0 ? 'M' : 'L'}${round(x(i))} ${round(y(pick(point)))}`).join(' ');
  const area = (path: string) => `${path} L${PLOT_W} ${PLOT_H} L0 ${PLOT_H} Z`;

  const totalLine = line((point) => point.total);
  const resolvedLine = line((point) => point.resolved);

  const peakIndex = daily.reduce(
    (best, point, i) => (point.total > daily[best].total ? i : best),
    0,
  );

  return {
    totalLine,
    totalArea: area(totalLine),
    resolvedLine,
    resolvedArea: area(resolvedLine),
    grid: Array.from({ length: GRID_STEPS + 1 }, (_, i) => (i / GRID_STEPS) * PLOT_H),
    yTicks: Array.from({ length: GRID_STEPS + 1 }, (_, i) =>
      axisNumber(((GRID_STEPS - i) / GRID_STEPS) * ceiling),
    ),
    xTicks: xTicks(daily),
    peak: {
      leftPct: (peakIndex / last) * 100,
      topPct: (y(daily[peakIndex].total) / PLOT_H) * 100,
    },
  };
}

/** Weekly, plus whatever the last day is -- five labels across a month. */
function xTicks(daily: DailyPoint[]): AxisTick[] {
  const last = daily.length - 1;
  const indices = [...new Set([0, 7, 14, 21, last])].filter((i) => i <= last);
  return indices.map((i) => ({
    label: dayLabel(daily[i].date),
    atPct: (i / last) * 100,
    anchor: i === 0 ? 'start' : i === last ? 'end' : 'middle',
  }));
}

/** "2026-05-08" -> "May 08". */
function dayLabel(date: string): string {
  const [, month, day] = date.split('-');
  return `${MONTHS[Number(month) - 1] ?? month} ${day}`;
}

/** Axis labels are read, not compared: "6k" beats "6,000" at this size. */
function axisNumber(value: number): string {
  if (value === 0) {
    return '0';
  }
  if (value >= 1000) {
    return `${round(value / 1000)}k`;
  }
  return String(round(value));
}

function round(value: number): number {
  return Math.round(value * 10) / 10;
}
