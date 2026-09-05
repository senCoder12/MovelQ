import { DatePipe } from '@angular/common';
import { Component, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { NzTableModule } from 'ng-zorro-antd/table';

import { AlertsStateService } from '../../core/alerts-state.service';
import { AlertsService } from '../../core/alerts.service';
import { AlertDeliveryView, AlertStatus, AlertView } from '../../core/alerts.model';
import { ShellService } from '../../core/shell.service';
import { TenantService } from '../../core/tenant.service';

/**
 * Every alert the tenant has fired -- the artifact that proves alerting
 * actually decided something without anyone opening the app. A row expands
 * to the exact rendered delivery (subject, body, who it would have gone
 * to) exactly as ScanService stored it; Acknowledge and Mute are inline,
 * one alert at a time, no bulk action.
 */
@Component({
  selector: 'app-alerts-page',
  standalone: true,
  imports: [NzTableModule, DatePipe, FormsModule],
  templateUrl: './alerts-page.component.html',
  styleUrl: './alerts-page.component.css',
})
export class AlertsPageComponent {
  private readonly alertsService = inject(AlertsService);
  private readonly alertsState = inject(AlertsStateService);
  private readonly route = inject(ActivatedRoute);
  private readonly shell = inject(ShellService);
  private readonly tenants = inject(TenantService);

  readonly alerts = signal<AlertView[]>([]);
  readonly error = signal<string | null>(null);
  readonly loading = signal(false);
  readonly statusFilter = signal<AlertStatus | 'all'>('all');

  readonly expanded = signal<ReadonlySet<string>>(new Set());
  readonly deliveries = signal<ReadonlyMap<string, AlertDeliveryView>>(new Map());
  readonly deliveryLoading = signal<ReadonlySet<string>>(new Set());

  /** The alert currently showing its inline mute form, or null. */
  readonly mutingAlertId = signal<string | null>(null);
  readonly muteReason = signal('');
  readonly muteDays = signal(7);

  readonly statusOptions: readonly (AlertStatus | 'all')[] = ['all', 'NEW', 'ACKNOWLEDGED', 'MUTED', 'EXPIRED'];

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

  selectStatus(status: AlertStatus | 'all'): void {
    this.statusFilter.set(status);
  }

  isExpanded(alertId: string): boolean {
    return this.expanded().has(alertId);
  }

  toggleExpand(alertId: string): void {
    const next = new Set(this.expanded());
    if (next.has(alertId)) {
      next.delete(alertId);
    } else {
      next.add(alertId);
      this.loadDelivery(alertId);
    }
    this.expanded.set(next);
  }

  deliveryFor(alertId: string): AlertDeliveryView | null {
    return this.deliveries().get(alertId) ?? null;
  }

  isDeliveryLoading(alertId: string): boolean {
    return this.deliveryLoading().has(alertId);
  }

  isRepeatPending(alert: AlertView): boolean {
    return alert.repeat_of !== null && alert.status === 'NEW';
  }

  acknowledge(alert: AlertView): void {
    this.alertsService.acknowledge(alert.alert_id).subscribe({
      next: () => {
        this.load();
        this.alertsState.refresh();
      },
    });
  }

  startMute(alertId: string): void {
    this.mutingAlertId.set(alertId);
    this.muteReason.set('');
    this.muteDays.set(7);
  }

  cancelMute(): void {
    this.mutingAlertId.set(null);
  }

  confirmMute(alert: AlertView): void {
    const reason = this.muteReason().trim();
    if (!reason || this.muteDays() < 1) {
      return;
    }
    this.alertsService.mute(alert.alert_id, { reason, days: this.muteDays() }).subscribe({
      next: () => {
        this.mutingAlertId.set(null);
        this.load();
        this.alertsState.refresh();
      },
    });
  }

  private loadDelivery(alertId: string): void {
    if (this.deliveries().has(alertId) || this.deliveryLoading().has(alertId)) {
      return;
    }
    this.deliveryLoading.update((set) => new Set(set).add(alertId));
    this.alertsService.getDelivery(alertId).subscribe({
      next: (delivery) => {
        this.deliveries.update((map) => new Map(map).set(alertId, delivery));
        this.deliveryLoading.update((set) => {
          const next = new Set(set);
          next.delete(alertId);
          return next;
        });
      },
      error: () => {
        this.deliveryLoading.update((set) => {
          const next = new Set(set);
          next.delete(alertId);
          return next;
        });
      },
    });
  }

  private load(): void {
    this.loading.set(true);
    const status = this.statusFilter();
    this.alertsService.list(status === 'all' ? undefined : status).subscribe({
      next: (alerts) => {
        this.alerts.set(alerts);
        this.error.set(null);
        this.loading.set(false);
        this.openFromQueryParam();
      },
      error: (err) => {
        this.alerts.set([]);
        this.error.set(err?.message ?? 'The backend is unreachable.');
        this.loading.set(false);
      },
    });
  }

  /** An insight card's "alerted HH:mm" chip links here with ?open=<id> --
   * expand that row once the list has loaded, so the delivery is visible
   * without a second click. */
  private openFromQueryParam(): void {
    const alertId = this.route.snapshot.queryParamMap.get('open');
    if (alertId && this.alerts().some((a) => a.alert_id === alertId) && !this.isExpanded(alertId)) {
      this.toggleExpand(alertId);
    }
  }
}
