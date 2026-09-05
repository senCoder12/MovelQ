import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';

import { DailyPoint, FleetSupplement } from './fleet-summary.model';
import { Period } from './shell.service';

/**
 * Where the insights page gets the figures the InsightPacket contract does not
 * carry. Injected as this abstract class, never as a concrete type: swapping
 * fixtures for the real endpoint is a one-line change in app.config.ts and
 * touches no component.
 */
export abstract class FleetSummarySource {
  abstract supplement(period: Period): Observable<FleetSupplement>;
}

/**
 * DEMO FIXTURE. Deterministic -- no randomness, so a reload never moves a line
 * on screen. Replace the provider in app.config.ts with an HttpFleetSummarySource
 * once the agent exposes a daily-series / review-outcome endpoint; nothing else
 * has to change.
 */
@Injectable({ providedIn: 'root' })
export class FixtureFleetSummarySource extends FleetSummarySource {
  supplement(period: Period): Observable<FleetSupplement> {
    return of({
      priorFlagged: 176_571,
      resolutionPct: 91.4,
      disputedInr: 1_820_000,
      daily: series(period),
    });
  }
}

/**
 * A month of anomaly counts: a slow decline across the window, a minor bump in
 * the second week and one mid-month incident peak. Closed form rather than a
 * literal table so any period length renders the same silhouette.
 */
function series(period: Period): DailyPoint[] {
  const [year, month] = period.split('-').map(Number);
  const days = new Date(year, month, 0).getDate();
  const last = days - 1;

  return Array.from({ length: days }, (_, i) => {
    const drift = 2300 - 700 * (i / last);
    const bump = 450 * Math.exp(-(((i - 7) / 3.2) ** 2));
    const spike = 3100 * Math.exp(-(((i - 14) / 4.4) ** 2));
    const total = Math.round(drift + bump + spike);
    // Verification catches up as the window ages: the oldest days have had the
    // longest to reconcile against telematics.
    const cleared = 0.7 + 0.06 * (i / last);
    return {
      date: `${year}-${pad(month)}-${pad(i + 1)}`,
      total,
      resolved: Math.round(total * cleared),
    };
  });
}

function pad(value: number): string {
  return String(value).padStart(2, '0');
}
