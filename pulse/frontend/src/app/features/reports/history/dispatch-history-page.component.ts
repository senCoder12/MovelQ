import { DatePipe } from '@angular/common';
import { Component, effect, inject, signal } from '@angular/core';
import { NzTableModule } from 'ng-zorro-antd/table';

import { DispatchView } from '../../../core/leadership.model';
import { LeadershipService } from '../../../core/leadership.service';
import { ShellService } from '../../../core/shell.service';
import { TenantService } from '../../../core/tenant.service';
import { EmailHtmlFrameComponent } from '../../../shared/email-html-frame/email-html-frame.component';

/**
 * Every leadership-pack dispatch in the tenant. A row expands to the exact
 * body_html that was stored at send time -- not a re-render of the current
 * pack -- since that stored copy is the audit artifact: it proves what was
 * actually transmitted, even after the underlying insights move on.
 */
@Component({
  selector: 'app-dispatch-history-page',
  standalone: true,
  imports: [NzTableModule, DatePipe, EmailHtmlFrameComponent],
  templateUrl: './dispatch-history-page.component.html',
  styleUrl: './dispatch-history-page.component.css',
})
export class DispatchHistoryPageComponent {
  private readonly leadershipService = inject(LeadershipService);
  private readonly shell = inject(ShellService);
  private readonly tenants = inject(TenantService);

  readonly dispatches = signal<DispatchView[]>([]);
  readonly error = signal<string | null>(null);
  readonly loading = signal(false);
  readonly expanded = signal<ReadonlySet<string>>(new Set());

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

  toggleExpand(dispatchId: string): void {
    const next = new Set(this.expanded());
    if (next.has(dispatchId)) {
      next.delete(dispatchId);
    } else {
      next.add(dispatchId);
    }
    this.expanded.set(next);
  }

  private load(): void {
    this.loading.set(true);
    this.leadershipService.getDispatchHistory().subscribe({
      next: (dispatches) => {
        this.dispatches.set(dispatches);
        this.error.set(null);
        this.loading.set(false);
      },
      error: (err) => {
        this.dispatches.set([]);
        this.error.set(err?.message ?? 'The backend is unreachable.');
        this.loading.set(false);
      },
    });
  }
}
