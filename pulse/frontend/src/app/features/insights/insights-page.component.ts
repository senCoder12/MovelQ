import { Component, effect, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { BriefService } from '../../core/brief.service';
import { formatCount } from '../../core/format';
import { InsightPacket } from '../../core/insight.model';
import { ShellService } from '../../core/shell.service';
import { TenantService } from '../../core/tenant.service';
import { SeverityBadgeComponent } from '../../shared/severity-badge/severity-badge.component';

/** Every insight in the tenant as a dense table -- the same packets the brief
 * renders as cards, at the density you scan rather than read. Picking a row
 * hands the insight back to the feed, which is where the detail lives. */
@Component({
  selector: 'app-insights-page',
  standalone: true,
  imports: [SeverityBadgeComponent],
  templateUrl: './insights-page.component.html',
  styleUrl: './insights-page.component.css',
})
export class InsightsPageComponent {
  private readonly briefService = inject(BriefService);
  private readonly router = inject(Router);
  private readonly shell = inject(ShellService);
  private readonly tenants = inject(TenantService);

  readonly insights = signal<InsightPacket[]>([]);
  readonly error = signal<string | null>(null);
  readonly loading = signal(false);

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

  open(insight: InsightPacket): void {
    this.shell.requestInsight(insight.insight_id);
    this.router.navigateByUrl('/brief');
  }

  count(value: number): string {
    return formatCount(value);
  }

  private load(): void {
    this.loading.set(true);
    this.shell.loading.set(true);
    this.briefService.getBrief('ops').subscribe({
      next: (brief) => {
        this.insights.set(brief.insights);
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
        this.shell.agentStatus.set(null);
        this.shell.agentError.set(message);
        this.error.set(message);
        this.loading.set(false);
        this.shell.loading.set(false);
      },
    });
  }
}
