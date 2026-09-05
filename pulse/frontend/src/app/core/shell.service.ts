import { Injectable, signal } from '@angular/core';

import { InsightPacket } from './insight.model';

/** Reporting periods offered by the top-bar selector. Newest first. */
export const PERIODS = ['2026-07', '2026-06', '2026-05'] as const;

export type Period = (typeof PERIODS)[number];

/** The agent status line rendered in the centre of the top bar. Populated by
 * whichever view last loaded a brief -- it is the agent's state, not the view's. */
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

  /** Palette visibility. Owned here so any component can open it (⌘K, the hint chip). */
  readonly paletteOpen = signal(false);

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
