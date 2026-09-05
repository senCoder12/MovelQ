import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, effect, inject, signal } from '@angular/core';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzNotificationService } from 'ng-zorro-antd/notification';

import { LeadershipService } from '../../core/leadership.service';
import { LeadershipPack } from '../../core/leadership.model';
import { ShellService } from '../../core/shell.service';
import { TenantService } from '../../core/tenant.service';

type SeverityBand = 'low' | 'medium' | 'high';

@Component({
  selector: 'app-leadership-pack-page',
  standalone: true,
  imports: [NzIconModule, DatePipe, DecimalPipe],
  templateUrl: './leadership-pack-page.component.html',
  styleUrl: './leadership-pack-page.component.css',
})
export class LeadershipPackPageComponent {
  private readonly leadershipService = inject(LeadershipService);
  private readonly notification = inject(NzNotificationService);
  private readonly shell = inject(ShellService);
  private readonly tenants = inject(TenantService);

  readonly pack = signal<LeadershipPack | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly generatedAt = signal<Date | null>(null);

  readonly eyebrow = computed(() => {
    const pack = this.pack();
    if (!pack) {
      return '';
    }
    return `Mobility operations · ${pack.period} · ${pack.scope.sites.join(', ')}`;
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
      },
      error: (err) => {
        this.pack.set(null);
        this.error.set(err?.message ?? 'The backend is unreachable.');
        this.loading.set(false);
        this.shell.loading.set(false);
      },
    });
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

  send(): void {
    this.notification.info('Not wired up yet', 'Sending leadership packs is out of scope for this build.');
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
