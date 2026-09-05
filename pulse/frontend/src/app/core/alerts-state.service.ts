import { Injectable, computed, inject, signal } from '@angular/core';

import { AlertsService } from './alerts.service';
import { AlertView } from './alerts.model';

/** Every alert for the current tenant, kept in one signal so the rail badge,
 * an insight card's chip, and the alerts table all read the same list
 * instead of each fetching it separately. Reloaded on tenant switch / the
 * shell's refresh tick (see AppShellComponent), and patched in place the
 * instant an acknowledge or mute comes back, so the badge count updates
 * without a second round trip. */
@Injectable({ providedIn: 'root' })
export class AlertsStateService {
  private readonly alertsService = inject(AlertsService);

  private readonly alerts = signal<AlertView[]>([]);

  readonly all = this.alerts.asReadonly();

  readonly newCount = computed(() => this.alerts().filter((a) => a.status === 'NEW').length);

  /** Most recent alert (any status) fired for this insight, or null if the
   * insight has never fired one -- what the card's "alerted HH:mm" chip
   * (or its absence) is built from. */
  latestForInsight(insightId: string): AlertView | null {
    const matches = this.alerts()
      .filter((a) => a.insight_id === insightId)
      .sort((a, b) => new Date(b.fired_at).getTime() - new Date(a.fired_at).getTime());
    return matches[0] ?? null;
  }

  refresh(): void {
    this.alertsService.list().subscribe({
      next: (alerts) => this.alerts.set(alerts),
      // Badge/chip state just stays whatever it last was -- not worth a toast.
      error: () => undefined,
    });
  }

  updateOne(updated: AlertView): void {
    this.alerts.update((all) => all.map((a) => (a.alert_id === updated.alert_id ? updated : a)));
  }
}
