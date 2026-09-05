import { DatePipe } from '@angular/common';
import { Component, effect, inject, signal } from '@angular/core';
import { NzTableModule } from 'ng-zorro-antd/table';

import { ActionDraft, ActionStatus, ACTION_TYPE_LABEL } from '../../../core/actions.model';
import { ActionsService } from '../../../core/actions.service';
import { ShellService } from '../../../core/shell.service';
import { TenantService } from '../../../core/tenant.service';

/**
 * Every drafted action in the tenant, decided or not -- the artifact that
 * proves a human was in the loop. An EDITED_APPROVED row shows the agent's
 * original alongside the human's edit (decision.edited_body), never one in
 * place of the other, since ActionDraftService never overwrites the
 * original draft.
 */
@Component({
  selector: 'app-actions-audit-page',
  standalone: true,
  imports: [NzTableModule, DatePipe],
  templateUrl: './actions-audit-page.component.html',
  styleUrl: './actions-audit-page.component.css',
})
export class ActionsAuditPageComponent {
  private readonly actionsService = inject(ActionsService);
  private readonly shell = inject(ShellService);
  private readonly tenants = inject(TenantService);

  readonly actions = signal<ActionDraft[]>([]);
  readonly error = signal<string | null>(null);
  readonly loading = signal(false);
  readonly statusFilter = signal<ActionStatus | 'all'>('all');
  readonly expanded = signal<ReadonlySet<string>>(new Set());

  readonly statusOptions: readonly (ActionStatus | 'all')[] = [
    'all',
    'DRAFTED',
    'APPROVED',
    'EDITED_APPROVED',
    'REJECTED',
  ];

  constructor() {
    effect(
      () => {
        this.tenants.tenantId();
        this.shell.refreshTick();
        this.statusFilter();
        this.load();
      },
      { allowSignalWrites: true },
    );
  }

  selectStatus(status: ActionStatus | 'all'): void {
    this.statusFilter.set(status);
  }

  toggleExpand(actionId: string): void {
    const next = new Set(this.expanded());
    if (next.has(actionId)) {
      next.delete(actionId);
    } else {
      next.add(actionId);
    }
    this.expanded.set(next);
  }

  typeLabel(action: ActionDraft): string {
    return ACTION_TYPE_LABEL[action.type];
  }

  private load(): void {
    this.loading.set(true);
    const status = this.statusFilter();
    this.actionsService.audit(status === 'all' ? undefined : status).subscribe({
      next: (actions) => {
        this.actions.set(actions);
        this.error.set(null);
        this.loading.set(false);
      },
      error: (err) => {
        this.actions.set([]);
        this.error.set(err?.message ?? 'The backend is unreachable.');
        this.loading.set(false);
      },
    });
  }
}
