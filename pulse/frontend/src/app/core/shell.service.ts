import { Injectable, signal } from '@angular/core';

import { InsightPacket } from './insight.model';

/** Reporting periods offered by the top-bar selector. Newest first. */
export const PERIODS = ['2026-07', '2026-06', '2026-05'] as const;

/** Rail collapse state. Persisted so the choice survives a reload. */
const RAIL_STORAGE_KEY = 'pulse.rail-collapsed';

export type Period = (typeof PERIODS)[number];

/** The agent status line rendered in the centre of the top bar. Populated by
 * whichever view last loaded a brief -- it is the agent's state, not the view's. */
/** One button in the top bar's segmented filter. Published by whichever view
 * owns a filter; the shell only renders and reports clicks. */
export interface ShellSegment {
  key: string;
  label: string;
}

/** The pill beside the view title. A view that publishes one owns the whole
 * pill -- wording and tone -- and the shell's own agent/issue line stands down
 * while it is set. */
export interface ShellStatus {
  label: string;
  tone: 'ok' | 'warn' | 'danger';
}

export interface AgentStatus {
  generatedAt: string;
  scannedTrips: number;
  signalCount: number;
}

/**
 * Cross-shell state: what the top bar shows, what the command palette can jump
 * to, and the refresh pulse views reload on.
 *
 * Views do not read `refreshTick` imperatively -- they take it in an effect
 * alongside `TenantService.tenantId`, so a tenant switch and a refresh click
 * are the same code path.
 */
@Injectable({ providedIn: 'root' })
export class ShellService {
  readonly periods = PERIODS;

  /** Shown in the rail's lockup. Bumped by hand with the UI, not the API. */
  readonly version = '3.4';

  readonly viewTitle = signal('Brief');
  readonly period = signal<Period>(PERIODS[0]);
  readonly loading = signal(false);
  readonly agentStatus = signal<AgentStatus | null>(null);
  readonly agentError = signal<string | null>(null);

  /** Top-bar segmented filter, owned by the active view. Empty = no filter. */
  readonly segments = signal<readonly ShellSegment[]>([]);
  readonly activeSegment = signal<string | null>(null);

  /** Status pill beside the view title, owned by the active view. */
  readonly status = signal<ShellStatus | null>(null);

  /** Palette visibility. Owned here so any component can open it (⌘K, the hint chip). */
  readonly paletteOpen = signal(false);

  /**
   * Rail collapsed to icons only. Lives here rather than in the shell component
   * so a view can read the rail's width state without reaching for its parent.
   */
  readonly railCollapsed = signal(restoreRailCollapsed());

  /** Headline-searchable insights, published by the brief feed as it loads. */
  readonly insights = signal<InsightPacket[]>([]);

  /** Set when the palette picks an insight; the brief feed consumes and clears it. */
  readonly pendingInsightId = signal<string | null>(null);

  private readonly refreshCount = signal(0);
  readonly refreshTick = this.refreshCount.asReadonly();

  refresh(): void {
    this.refreshCount.update((tick) => tick + 1);
  }

  setPeriod(period: Period): void {
    if (period === this.period()) {
      return;
    }
    this.period.set(period);
  }

  /**
   * Publish a view's top-bar controls. Called on init and again -- with empty
   * segments and a null status -- on destroy, so a view never leaves its own
   * filter behind in the bar of the next one.
   */
  setSegments(segments: readonly ShellSegment[], active: string | null = null): void {
    this.segments.set(segments);
    this.activeSegment.set(active);
  }

  selectSegment(key: string): void {
    this.activeSegment.set(key);
  }

  setStatus(status: ShellStatus | null): void {
    this.status.set(status);
  }

  toggleRail(): void {
    this.setRailCollapsed(!this.railCollapsed());
  }

  setRailCollapsed(collapsed: boolean): void {
    this.railCollapsed.set(collapsed);
    try {
      localStorage.setItem(RAIL_STORAGE_KEY, collapsed ? '1' : '0');
    } catch {
      // Storage disabled: the choice still applies for this session.
    }
  }

  openPalette(): void {
    this.paletteOpen.set(true);
  }

  closePalette(): void {
    this.paletteOpen.set(false);
  }

  requestInsight(insightId: string): void {
    this.pendingInsightId.set(insightId);
  }

  consumeInsightRequest(): void {
    this.pendingInsightId.set(null);
  }
}

function restoreRailCollapsed(): boolean {
  try {
    return localStorage.getItem(RAIL_STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}
