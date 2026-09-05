import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, effect, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzNotificationService } from 'ng-zorro-antd/notification';

import { LeadershipService } from '../../core/leadership.service';
import { DispatchApiResponse, DispatchView, LeadershipPack } from '../../core/leadership.model';
import { ShellService } from '../../core/shell.service';
import { TenantService } from '../../core/tenant.service';
import { SendReportDrawerComponent } from '../reports/send/send-report-drawer.component';

type SeverityBand = 'low' | 'medium' | 'high';

@Component({
  selector: 'app-leadership-pack-page',
  standalone: true,
  imports: [NzIconModule, DatePipe, DecimalPipe, SendReportDrawerComponent],
  templateUrl: './leadership-pack-page.component.html',
  styleUrl: './leadership-pack-page.component.css',
})
export class LeadershipPackPageComponent {
  private readonly leadershipService = inject(LeadershipService);
  private readonly notification = inject(NzNotificationService);
  private readonly router = inject(Router);
  private readonly shell = inject(ShellService);
  private readonly tenants = inject(TenantService);

  readonly pack = signal<LeadershipPack | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly generatedAt = signal<Date | null>(null);

  readonly sendDrawerVisible = signal(false);
  /** The most recent dispatch for the period on screen -- seeded from
   * history on load, then updated in place the instant a new one is
   * recorded, so the chip survives a reload without a second endpoint. */
  readonly latestDispatch = signal<DispatchView | null>(null);

  /** Exposed for the send drawer's [period] binding -- templates cannot
   * reach a private field, and the drawer needs to know which period it is
   * sending. */
  readonly period = computed(() => this.shell.period());

  readonly eyebrow = computed(() => {
    const pack = this.pack();
    if (!pack) {
      return '';
    }
    return `Mobility operations · ${pack.period} · ${pack.scope.sites.join(', ')}`;
  });

  readonly dispatchChipLabel = computed(() => {
    const dispatch = this.latestDispatch();
    if (!dispatch) {
      return null;
    }
    const time = new Date(dispatch.dispatched_at).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
    const verb = dispatch.status === 'FAILED' ? 'Failed' : dispatch.transport === 'smtp' ? 'Sent' : 'Recorded';
    const count = dispatch.recipients.length;
    return `${verb} ${time} · ${count} recipient${count === 1 ? '' : 's'}`;
  });

  constructor() {
    // The pack is the one period-aware view, so the top bar's period selector
    // reloads it alongside the usual tenant-switch / refresh triggers.
    effect(
      () => {
        this.shell.period();
        this.tenants.tenantId();
        this.shell.refreshTick();
        this.refresh();
      },
      { allowSignalWrites: true },
    );
  }

  refresh(): void {
    this.loading.set(true);
    this.shell.loading.set(true);
    this.error.set(null);
    this.leadershipService.getLeadershipPack(this.shell.period()).subscribe({
      next: (pack) => {
        this.pack.set(pack);
        this.generatedAt.set(new Date());
        this.loading.set(false);
        this.shell.loading.set(false);
        this.loadLatestDispatch();
      },
      error: (err) => {
        this.pack.set(null);
        this.error.set(err?.message ?? 'The backend is unreachable.');
        this.loading.set(false);
        this.shell.loading.set(false);
      },
    });
  }

  private loadLatestDispatch(): void {
    this.leadershipService.getDispatchHistory(this.shell.period()).subscribe({
      next: (dispatches) => this.latestDispatch.set(dispatches[0] ?? null),
      // No toast on failure -- the chip just stays absent, which is the
      // same as "never dispatched" from the operator's point of view.
      error: () => this.latestDispatch.set(null),
    });
  }

  openSendDrawer(): void {
    this.sendDrawerVisible.set(true);
  }

  closeSendDrawer(): void {
    this.sendDrawerVisible.set(false);
  }

  onDispatched(response: DispatchApiResponse): void {
    this.latestDispatch.set(response.dispatch);
  }

  openHistory(): void {
    this.router.navigateByUrl('/reports/history');
  }

  severityBand(severity: number): SeverityBand {
    if (severity >= 80) {
      return 'high';
    }
    if (severity >= 50) {
      return 'medium';
    }
    return 'low';
  }

  copyAsText(): void {
    const pack = this.pack();
    if (!pack) {
      return;
    }
    navigator.clipboard.writeText(toPlainText(pack)).then(
      () => this.notification.success('Copied', 'Plain text copied to the clipboard.'),
      () => this.notification.error('Copy failed', 'Could not access the clipboard.'),
    );
  }

}

function toPlainText(pack: LeadershipPack): string {
  const lines: string[] = [];
  lines.push(`Mobility operations · ${pack.period} · ${pack.scope.sites.join(', ')}`);
  lines.push('');
  lines.push(pack.headline);
  lines.push('');
  lines.push(pack.summary);
  lines.push('');
  for (const tile of pack.tiles) {
    lines.push(`${tile.label}: ${tile.value} (${tile.reference})`);
  }
  lines.push('');
  lines.push('What needs a decision');
  for (const finding of pack.findings) {
    lines.push('');
    lines.push(`${finding.title} [severity ${finding.severity}]`);
    lines.push(finding.body);
    lines.push(`Recommendation: ${finding.recommendation}`);
  }
  lines.push('');
  lines.push(
    `Computed from ${pack.footer.computed_from_trips.toLocaleString('en-US')} trips, ` +
      `${pack.footer.excluded_trips.toLocaleString('en-US')} excluded (${pack.footer.excluded_pct}%).`,
  );
  if (pack.footer.exclusion_reasons.length > 0) {
    lines.push(pack.footer.exclusion_reasons.join('; '));
  }
  return lines.join('\n');
}
