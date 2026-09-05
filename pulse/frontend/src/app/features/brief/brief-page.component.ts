import { Component, HostListener, QueryList, ViewChildren, computed, effect, inject, signal } from '@angular/core';
import { forkJoin } from 'rxjs';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzNotificationService } from 'ng-zorro-antd/notification';
import { NzSkeletonModule } from 'ng-zorro-antd/skeleton';

import { ActionDraft, ActionType } from '../../core/actions.model';
import { ActionsService } from '../../core/actions.service';
import { ActionsStateService } from '../../core/actions-state.service';
import { BriefService } from '../../core/brief.service';
import { Domain, shapeOf, summaryTiles } from '../../core/insight-presentation';
import { InsightPacket } from '../../core/insight.model';
import { ShellService } from '../../core/shell.service';
import { TenantService } from '../../core/tenant.service';
import { ActionDrawerComponent } from '../actions/action-drawer.component';
import { InsightCardComponent } from '../../shared/insight-card/insight-card.component';
import { TraceDrawerComponent } from '../trace/trace-drawer.component';

/** Filter tabs above the feed. 'all' is the default and is never hidden. */
type FilterKey = 'all' | Domain;

interface FilterTab {
  key: FilterKey;
  label: string;
  count: number;
}

/**
 * The decision feed: three summary tiles rolling up the domains, then one card
 * per insight. Keyboard-first -- j/k move the cursor, Enter opens the trace
 * drawer for the card under it, Escape closes whatever is open.
 */
@Component({
  selector: 'app-brief-page',
  standalone: true,
  imports: [NzSkeletonModule, NzIconModule, InsightCardComponent, TraceDrawerComponent, ActionDrawerComponent],
  templateUrl: './brief-page.component.html',
  styleUrl: './brief-page.component.css',
})
export class BriefPageComponent {
  private readonly actionsService = inject(ActionsService);
  private readonly actionsState = inject(ActionsStateService);
  private readonly briefService = inject(BriefService);
  private readonly notification = inject(NzNotificationService);
  private readonly shell = inject(ShellService);
  private readonly tenants = inject(TenantService);

  @ViewChildren(InsightCardComponent) private cards?: QueryList<InsightCardComponent>;

  readonly insights = signal<InsightPacket[] | null>(null);
  readonly loading = signal(false);
  readonly filter = signal<FilterKey>('all');

  /** j/k cursor, indexed against the *visible* list. -1 means nothing selected. */
  readonly cursor = signal(-1);

  readonly drawerVisible = signal(false);
  readonly traceInsight = signal<InsightPacket | null>(null);

  readonly actionDrawerVisible = signal(false);
  readonly actionDraft = signal<ActionDraft | null>(null);
  /** `${insight_id}::${type}` of the button awaiting a draft, so only that
   * one card shows a pending state while the agent call is in flight. */
  readonly pendingActionKey = signal<string | null>(null);

  readonly tiles = computed(() => summaryTiles(this.insights() ?? []));

  readonly visible = computed(() => {
    const all = this.insights() ?? [];
    const key = this.filter();
    return key === 'all' ? all : all.filter((insight) => shapeOf(insight).domain === key);
  });

  readonly tabs = computed<FilterTab[]>(() => {
    const all = this.insights() ?? [];
    const count = (domain: Domain) =>
      all.filter((insight) => shapeOf(insight).domain === domain).length;
    const tabs: FilterTab[] = [
      { key: 'all', label: 'All issues', count: all.length },
      { key: 'operational', label: 'Operations', count: count('operational') },
      { key: 'safety', label: 'Safety', count: count('safety') },
      { key: 'financial', label: 'Billing', count: count('financial') },
    ];
    return tabs.filter((tab) => tab.key === 'all' || tab.count > 0);
  });

  constructor() {
    // One reload path for all triggers: first render, tenant switch, refresh.
    effect(
      () => {
        this.tenants.tenantId();
        this.shell.refreshTick();
        this.load();
      },
      { allowSignalWrites: true },
    );

    // The command palette picks an insight by headline; the feed is what can
    // actually show it, so it consumes the request here.
    effect(
      () => {
        const insightId = this.shell.pendingInsightId();
        if (!insightId) {
          return;
        }
        const index = this.visible().findIndex((item) => item.insight_id === insightId);
        if (index < 0) {
          return;
        }
        this.shell.consumeInsightRequest();
        this.cursor.set(index);
        this.scrollToCursor();
      },
      { allowSignalWrites: true },
    );
  }

  @HostListener('document:keydown', ['$event'])
  onKeydown(event: KeyboardEvent): void {
    if (this.shell.paletteOpen() || event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }
    if (isTypingTarget(event.target)) {
      return;
    }
    if (event.key === 'Escape' && this.drawerVisible()) {
      event.preventDefault();
      this.closeDrawer();
      return;
    }
    if (this.drawerVisible()) {
      return;
    }

    const count = this.visible().length;
    if (count === 0) {
      return;
    }
    switch (event.key) {
      case 'j':
        event.preventDefault();
        this.moveCursor(1, count);
        break;
      case 'k':
        event.preventDefault();
        this.moveCursor(-1, count);
        break;
      case 'Enter': {
        const insight = this.visible()[this.cursor()];
        if (insight) {
          event.preventDefault();
          this.openTrace(insight.insight_id);
        }
        break;
      }
      default:
        break;
    }
  }

  selectFilter(key: FilterKey): void {
    this.filter.set(key);
    this.cursor.set(this.visible().length > 0 ? 0 : -1);
  }

  /** A summary tile jumps the cursor to the insight it rolls up. */
  focusTile(insightId: string): void {
    this.filter.set('all');
    const index = (this.insights() ?? []).findIndex((item) => item.insight_id === insightId);
    if (index < 0) {
      return;
    }
    this.cursor.set(index);
    this.scrollToCursor();
  }

  openTrace(insightId: string): void {
    const index = this.visible().findIndex((item) => item.insight_id === insightId);
    if (index >= 0) {
      this.cursor.set(index);
    }
    this.traceInsight.set(this.visible()[index] ?? null);
    this.drawerVisible.set(true);
  }

  closeDrawer(): void {
    this.drawerVisible.set(false);
  }

  onDraftRequested(insight: InsightPacket, type: ActionType): void {
    const key = `${insight.insight_id}::${type}`;
    if (this.pendingActionKey()) {
      return;
    }
    this.pendingActionKey.set(key);
    this.actionsService.draft(insight.insight_id, type).subscribe({
      next: (draft) => {
        this.pendingActionKey.set(null);
        this.actionDraft.set(draft);
        this.actionDrawerVisible.set(true);
      },
      error: (err) => {
        this.pendingActionKey.set(null);
        this.notification.error(
          'Unable to draft action',
          err?.error?.message ?? err?.message ?? 'The backend is unreachable.',
        );
      },
    });
  }

  closeActionDrawer(): void {
    this.actionDrawerVisible.set(false);
  }

  onActionDecided(draft: ActionDraft): void {
    this.actionsState.record(draft);
  }

  private moveCursor(delta: number, count: number): void {
    const next = this.cursor() < 0 ? 0 : Math.min(count - 1, Math.max(0, this.cursor() + delta));
    this.cursor.set(next);
    this.scrollToCursor();
  }

  private scrollToCursor(): void {
    // Wait for the class binding to land before asking the card to scroll.
    queueMicrotask(() => this.cards?.get(this.cursor())?.scrollIntoView());
  }

  /** Seeds ActionsStateService from every visible insight's action history,
   * so a card already shows "... approved 14:32" right after a reload
   * instead of only after a decision made in this session. */
  private seedActionsState(insights: InsightPacket[]): void {
    if (insights.length === 0) {
      return;
    }
    forkJoin(insights.map((insight) => this.actionsService.listForInsight(insight.insight_id))).subscribe({
      next: (perInsight) => this.actionsState.seed(perInsight.flat()),
      error: () => {
        // Button state degrades to "never drafted" for this load; the next
        // decision (or the next reload) re-seeds it. Not worth a toast.
      },
    });
  }

  private load(): void {
    this.loading.set(true);
    this.shell.loading.set(true);
    this.briefService.getBrief('ops').subscribe({
      next: (brief) => {
        this.insights.set(brief.insights);
        this.cursor.set(brief.insights.length > 0 ? 0 : -1);
        this.shell.insights.set(brief.insights);
        this.shell.agentError.set(null);
        this.shell.agentStatus.set({
          generatedAt: brief.generated_at,
          scannedTrips: brief.insights.reduce((max, insight) => Math.max(max, insight.metric.n), 0),
          signalCount: brief.insights.length,
        });
        this.loading.set(false);
        this.shell.loading.set(false);
        this.seedActionsState(brief.insights);
      },
      error: (err) => {
        const message = err?.message ?? 'The backend is unreachable.';
        this.insights.set(null);
        this.cursor.set(-1);
        this.shell.insights.set([]);
        this.shell.agentStatus.set(null);
        this.shell.agentError.set(message);
        this.loading.set(false);
        this.shell.loading.set(false);
        this.notification.error('Unable to load brief', message);
      },
    });
  }
}

/** True when the key event came from a field the operator is typing into. */
function isTypingTarget(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  if (!element) {
    return false;
  }
  return (
    element.isContentEditable ||
    element.tagName === 'INPUT' ||
    element.tagName === 'TEXTAREA' ||
    element.tagName === 'SELECT'
  );
}
