import { Component, computed, effect, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { catchError, forkJoin, of } from 'rxjs';

import { BriefService } from '../../core/brief.service';
import { formatCompactInr, formatCount, formatPct } from '../../core/format';
import { Confidence, DataQualityEntry, InsightPacket } from '../../core/insight.model';
import { severityLabel, shapeOf } from '../../core/insight-presentation';
import { ShellService } from '../../core/shell.service';
import { TenantService } from '../../core/tenant.service';

type Band = 'high' | 'medium' | 'low';
type Filter = 'all' | 'high' | 'medium';
type Tone = 'danger' | 'warn' | 'ok' | 'muted';

/** One row of the signal table: the detector's finding, plus the exclusion
 * numbers that say how much of the fleet it was computed from. */
export interface SignalRow {
  insightId: string;
  /** Display code -- ins_001 -> "INS-01". */
  code: string;
  metricId: string;
  title: string;
  description: string;
  trips: number;
  /** Second line under the volume: the rate that makes the count mean something. */
  qualifier: string;
  qualifierTone: Tone;
  severity: number;
  severityLabel: string;
  band: Band;
  excludedPct: number;
  confidence: Confidence;
}

const PAGE_SIZE = 8;

const MONTHS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

/**
 * Data quality as the operator reads it: how much of the telemetry is clean at
 * the top, then every signal the detectors raised against it, ranked by
 * severity. The table is the page -- the three cards above it are the same
 * numbers rolled up, not extra data.
 */
@Component({
  selector: 'app-data-quality-page',
  standalone: true,
  imports: [NzIconModule],
  templateUrl: './data-quality-page.component.html',
  styleUrl: './data-quality-page.component.css',
})
export class DataQualityPageComponent {
  private readonly briefService = inject(BriefService);
  private readonly router = inject(Router);
  private readonly shell = inject(ShellService);
  private readonly tenants = inject(TenantService);

  readonly insights = signal<InsightPacket[]>([]);
  readonly entries = signal<DataQualityEntry[]>([]);
  readonly error = signal<string | null>(null);
  readonly loading = signal(false);

  readonly query = signal('');
  readonly filter = signal<Filter>('all');
  readonly page = signal(1);

  /** Every signal, worst first. The table's source of truth. */
  readonly rows = computed<SignalRow[]>(() => {
    const quality = new Map(this.entries().map((entry) => [entry.insight_id, entry.data_quality]));
    return this.insights()
      .map((insight) => {
        // The dedicated endpoint wins when it answers; the packet's own copy is
        // the fallback, so one failed call does not blank the column.
        const dataQuality = quality.get(insight.insight_id) ?? insight.data_quality;
        const shape = shapeOf(insight);
        const band = bandOf(insight.severity);
        return {
          insightId: insight.insight_id,
          code: signalCode(insight.insight_id),
          metricId: insight.metric.id,
          title: shape.category,
          description: shape.summary,
          trips: insight.impact.affected_trips ?? insight.metric.n,
          qualifier: qualifierOf(insight, band),
          qualifierTone: band === 'low' ? ('muted' as const) : toneOf(band),
          severity: insight.severity,
          severityLabel: severityLabel(insight.severity),
          band,
          excludedPct: dataQuality.excluded_pct,
          confidence: dataQuality.confidence,
        };
      })
      .sort((a, b) => b.severity - a.severity);
  });

  readonly highCount = computed(() => this.rows().filter((row) => row.band === 'high').length);
  readonly mediumCount = computed(() => this.rows().filter((row) => row.band === 'medium').length);

  readonly filtered = computed<SignalRow[]>(() => {
    const needle = this.query().trim().toLowerCase();
    const band = this.filter();
    return this.rows().filter((row) => {
      if (band !== 'all' && row.band !== band) {
        return false;
      }
      if (!needle) {
        return true;
      }
      return `${row.code} ${row.title} ${row.description} ${row.metricId}`
        .toLowerCase()
        .includes(needle);
    });
  });

  readonly pageCount = computed(() => Math.max(1, Math.ceil(this.filtered().length / PAGE_SIZE)));

  readonly pageRows = computed<SignalRow[]>(() => {
    const start = (Math.min(this.page(), this.pageCount()) - 1) * PAGE_SIZE;
    return this.filtered().slice(start, start + PAGE_SIZE);
  });

  // --- The three cards -------------------------------------------------------

  /** Share of scanned rows that survived exclusion, weighted by sample size:
   * a detector that excluded 3% of two million rows outweighs one that excluded
   * 30% of two hundred. */
  readonly integrity = computed(() => {
    const insights = this.insights();
    const byInsight = new Map(this.rows().map((row) => [row.insightId, row.excludedPct]));
    let scanned = 0;
    let excluded = 0;
    for (const insight of insights) {
      const pct = byInsight.get(insight.insight_id) ?? insight.data_quality.excluded_pct;
      scanned += insight.metric.n;
      excluded += (insight.metric.n * pct) / 100;
    }
    return scanned === 0 ? 100 : ((scanned - excluded) / scanned) * 100;
  });

  readonly integrityValue = computed(() => (Math.round(this.integrity() * 10) / 10).toString());

  readonly integrityBadge = computed(() => {
    const value = this.integrity();
    if (value >= 98) {
      return { label: 'Healthy', tone: 'ok' as const };
    }
    if (value >= 95) {
      return { label: 'Monitor', tone: 'warn' as const };
    }
    return { label: 'Degraded', tone: 'danger' as const };
  });

  readonly signalCount = computed(() => this.rows().length);

  readonly signalBadge = computed(() =>
    this.highCount() > 0
      ? { label: 'Needs attention', tone: 'warn' as const }
      : { label: 'Stable', tone: 'ok' as const },
  );

  /** "2 high priority · 1 medium" -- bands with nothing in them are dropped. */
  readonly priorityLine = computed(() => {
    const low = this.rows().filter((row) => row.band === 'low').length;
    const parts: string[] = [];
    if (this.highCount() > 0) {
      parts.push(`${this.highCount()} high priority`);
    }
    if (this.mediumCount() > 0) {
      parts.push(`${this.mediumCount()} medium`);
    }
    if (low > 0) {
      parts.push(`${low} low`);
    }
    return parts.length > 0 ? parts.join(' · ') : 'No open signals';
  });

  /** The widest denominator any detector ran against -- the fleet under audit. */
  readonly monitoredTrips = computed(() =>
    this.insights().reduce((max, insight) => Math.max(max, insight.metric.n), 0),
  );

  readonly periodLabel = computed(() => {
    const [year, month] = this.shell.period().split('-');
    return `${MONTHS[Number(month) - 1] ?? month} ${year}`;
  });

  constructor() {
    effect(
      () => {
        this.tenants.tenantId();
        this.shell.refreshTick();
        this.load();
      },
      { allowSignalWrites: true },
    );
  }

  // --- Controls --------------------------------------------------------------

  setQuery(value: string): void {
    this.query.set(value);
    this.page.set(1);
  }

  setFilter(filter: Filter): void {
    this.filter.set(filter);
    this.page.set(1);
  }

  previous(): void {
    this.page.update((page) => Math.max(1, page - 1));
  }

  next(): void {
    this.page.update((page) => Math.min(this.pageCount(), page + 1));
  }

  /** The detail lives in the brief feed, so reviewing a signal hands the
   * insight back to it rather than duplicating the card here. */
  review(row: SignalRow): void {
    this.shell.requestInsight(row.insightId);
    this.router.navigateByUrl('/brief');
  }

  /** What is on screen, as the operator filtered it -- not the whole tenant. */
  export(): void {
    const header = [
      'signal',
      'insight_id',
      'metric_id',
      'title',
      'impacted_trips',
      'qualifier',
      'severity',
      'severity_band',
      'excluded_pct',
      'confidence',
    ];
    const lines = this.filtered().map((row) =>
      [
        row.code,
        row.insightId,
        row.metricId,
        row.title,
        row.trips,
        row.qualifier,
        row.severity,
        row.band,
        row.excludedPct,
        row.confidence,
      ]
        .map(csvCell)
        .join(','),
    );
    const blob = new Blob([[header.join(','), ...lines].join('\n')], {
      type: 'text/csv;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `data-quality-${this.tenants.tenantId()}-${this.shell.period()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  count(value: number): string {
    return formatCount(value);
  }

  private load(): void {
    this.loading.set(true);
    this.shell.loading.set(true);
    forkJoin({
      brief: this.briefService.getBrief('ops'),
      quality: this.briefService.getDataQuality().pipe(catchError(() => of({ entries: [] }))),
    }).subscribe({
      next: ({ brief, quality }) => {
        this.insights.set(brief.insights);
        this.entries.set(quality.entries);
        this.shell.insights.set(brief.insights);
        // Same feed as the brief, so the top bar keeps its agent status line
        // instead of reading idle while this view is open.
        this.shell.agentError.set(null);
        this.shell.agentStatus.set({
          generatedAt: brief.generated_at,
          scannedTrips: brief.insights.reduce((max, insight) => Math.max(max, insight.metric.n), 0),
          signalCount: brief.insights.length,
        });
        this.error.set(null);
        this.page.set(1);
        this.loading.set(false);
        this.shell.loading.set(false);
      },
      error: (err) => {
        const message = err?.message ?? 'The backend is unreachable.';
        this.insights.set([]);
        this.entries.set([]);
        this.shell.agentStatus.set(null);
        this.shell.agentError.set(message);
        this.error.set(message);
        this.loading.set(false);
        this.shell.loading.set(false);
      },
    });
  }
}

function bandOf(severity: number): Band {
  if (severity >= 80) {
    return 'high';
  }
  if (severity >= 50) {
    return 'medium';
  }
  return 'low';
}

function toneOf(band: Band): Tone {
  return band === 'high' ? 'danger' : band === 'medium' ? 'warn' : 'ok';
}

/** "ins_001" -> "INS-01". An id that carries no trailing number is shown as-is. */
function signalCode(insightId: string): string {
  const match = insightId.match(/(\d+)$/);
  if (!match) {
    return insightId.toUpperCase();
  }
  return `INS-${String(Number(match[1])).padStart(2, '0')}`;
}

/**
 * The rate under the trip count. Money first (a billing gap reads as rupees,
 * not as a percentage), then coverage metrics as their shortfall, then the
 * metric's own rate. A low-severity signal reads as a share of the fleet --
 * the point of it is that it is small.
 */
function qualifierOf(insight: InsightPacket, band: Band): string {
  const { impact, metric } = insight;
  if (impact.cost_inr_month !== undefined) {
    return `${formatCompactInr(impact.cost_inr_month)} overcharge`;
  }
  if (band === 'low' && impact.affected_trips !== undefined && metric.n > 0) {
    return `${formatPct((impact.affected_trips / metric.n) * 100)} of fleet`;
  }
  if (shapeOf(insight).tileKind === 'gap') {
    return `${formatPct(100 - metric.value)} non-compliance`;
  }
  return `${formatPct(metric.value)} fleet error`;
}

function csvCell(value: string | number): string {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}
