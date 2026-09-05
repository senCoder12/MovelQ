import { Component, computed, effect, inject, signal } from '@angular/core';

import { BriefService } from '../../core/brief.service';
import { formatCount, formatPct } from '../../core/format';
import { InsightPacket, ValidationStatus } from '../../core/insight.model';
import { ShellService } from '../../core/shell.service';
import { TenantService } from '../../core/tenant.service';

interface AuditRow {
  queryId: string;
  insightId: string;
  metricId: string;
  numerator: number;
  denominator: number;
  ratio: number;
  status: ValidationStatus;
  notes: string;
  exclusions: string[];
}

/**
 * Every query behind every current finding, flattened into one ledger. This is
 * the same trace the drawer shows per insight -- here it is the whole audit
 * surface at once, which is what someone reconciling a month actually wants.
 */
@Component({
  selector: 'app-audit-page',
  standalone: true,
  templateUrl: './audit-page.component.html',
  styleUrl: './audit-page.component.css',
})
export class AuditPageComponent {
  private readonly briefService = inject(BriefService);
  private readonly shell = inject(ShellService);
  private readonly tenants = inject(TenantService);

  readonly insights = signal<InsightPacket[]>([]);
  readonly error = signal<string | null>(null);
  readonly loading = signal(false);

  readonly rows = computed<AuditRow[]>(() =>
    this.insights().flatMap((insight) =>
      insight.trace.map((entry) => ({
        queryId: entry.query_id,
        insightId: insight.insight_id,
        metricId: insight.metric.id,
        numerator: entry.numerator,
        denominator: entry.denominator,
        ratio: entry.denominator === 0 ? 0 : (entry.numerator / entry.denominator) * 100,
        status: entry.validation.status,
        notes: entry.validation.notes,
        exclusions: entry.exclusions,
      })),
    ),
  );

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

  count(value: number): string {
    return formatCount(value);
  }

  pct(value: number): string {
    return formatPct(value);
  }

  private load(): void {
    this.loading.set(true);
    this.shell.loading.set(true);
    this.briefService.getBrief('ops').subscribe({
      next: (brief) => {
        this.insights.set(brief.insights);
        this.shell.insights.set(brief.insights);
        this.error.set(null);
        this.loading.set(false);
        this.shell.loading.set(false);
      },
      error: (err) => {
        this.insights.set([]);
        this.error.set(err?.message ?? 'The backend is unreachable.');
        this.loading.set(false);
        this.shell.loading.set(false);
      },
    });
  }
}
