import { Component, HostListener, computed, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  ActivatedRoute,
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive,
  RouterOutlet,
} from '@angular/router';
import { NzDropDownModule } from 'ng-zorro-antd/dropdown';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { filter } from 'rxjs';

import { formatCompact } from '../core/format';
import { HealthService } from '../core/health.service';
import { Period, ShellService } from '../core/shell.service';
import { ThemeMode, ThemeService } from '../core/theme.service';
import { TenantId, TenantService } from '../core/tenant.service';
import { CommandPaletteComponent } from './command-palette.component';
import { NAV_GROUPS } from './nav';

/** Human label for a period key ("2026-07" -> "Last 30 days (Jul 2026)"). */
const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/**
 * Three-zone application shell: a persistent left rail, a sticky top bar, and
 * the only scrolling region in the app (the content zone). Nothing here scrolls
 * away, so the agent's headline count and the tenant in scope stay on screen.
 */
@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    NzIconModule,
    NzDropDownModule,
    CommandPaletteComponent,
  ],
  templateUrl: './app-shell.component.html',
  styleUrl: './app-shell.component.css',
})
export class AppShellComponent {
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly healthService = inject(HealthService);

  readonly shell = inject(ShellService);
  readonly tenants = inject(TenantService);
  readonly theme = inject(ThemeService);

  readonly navGroups = NAV_GROUPS;
  readonly agentUp = signal<boolean | null>(null);

  /** Badge on the Brief nav item: how many signals are in the current feed. */
  readonly signalCount = computed(() => this.shell.insights().length);

  /** Worst confidence across the feed, colouring the Data health dot. */
  readonly healthTone = computed<'ok' | 'warn' | 'danger'>(() => {
    const confidences = this.shell.insights().map((insight) => insight.data_quality.confidence);
    if (confidences.includes('low')) {
      return 'danger';
    }
    if (confidences.includes('medium')) {
      return 'warn';
    }
    return 'ok';
  });

  readonly periodLabel = computed(() => label(this.shell.period()));

  /** Names what the toggle will do, not the state it is in. */
  readonly railToggleLabel = computed(() =>
    this.shell.railCollapsed() ? 'Expand sidebar' : 'Collapse sidebar',
  );

  /** The top bar's headline: how much is wrong, over how many trips. */
  readonly issueLine = computed(() => {
    const insights = this.shell.insights();
    if (insights.length === 0) {
      return null;
    }
    const highPriority = insights.filter((insight) => insight.severity >= 50).length;
    const scanned = insights.reduce((max, insight) => Math.max(max, insight.metric.n), 0);
    return `${highPriority} high-priority ${
      highPriority === 1 ? 'issue' : 'issues'
    } detected across ${formatCompact(scanned)} trips`;
  });

  constructor() {
    this.router.events
      .pipe(
        filter((event): event is NavigationEnd => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.shell.viewTitle.set(this.resolveViewTitle()));

    // Health follows the same reload path as everything else: a tenant switch
    // or a refresh click re-reads it.
    effect(
      () => {
        this.tenants.tenantId();
        this.shell.refreshTick();
        this.loadHealth();
      },
      { allowSignalWrites: true },
    );
  }

  @HostListener('document:keydown', ['$event'])
  onKeydown(event: KeyboardEvent): void {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      if (this.shell.paletteOpen()) {
        this.shell.closePalette();
      } else {
        this.shell.openPalette();
      }
      return;
    }
    if (event.key === 'Escape' && this.shell.paletteOpen()) {
      this.shell.closePalette();
    }
  }

  selectTenant(tenantId: TenantId): void {
    this.tenants.select(tenantId);
  }

  selectPeriod(period: Period): void {
    this.shell.setPeriod(period);
  }

  periodLabelFor(period: Period): string {
    return label(period);
  }

  /** Menu label for a theme mode. 'system' names what it follows, not itself. */
  themeLabelFor(mode: ThemeMode): string {
    return mode === 'system' ? 'Match system' : mode === 'dark' ? 'Dark' : 'Light';
  }

  refresh(): void {
    this.shell.refresh();
  }

  private loadHealth(): void {
    this.healthService.getHealth().subscribe({
      next: (health) => this.agentUp.set(health.agent?.status === 'UP'),
      error: () => this.agentUp.set(false),
    });
  }

  /** Deepest matched route carrying a `viewTitle`. */
  private resolveViewTitle(): string {
    let route = this.route.firstChild;
    let title = this.shell.viewTitle();
    while (route) {
      title = (route.snapshot.data['viewTitle'] as string | undefined) ?? title;
      route = route.firstChild;
    }
    return title;
  }
}

function label(period: Period): string {
  const [year, month] = period.split('-');
  const name = MONTHS[Number(month) - 1] ?? month;
  return `Last 30 days (${name} ${year})`;
}
