import { Component, computed, effect, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { BriefService } from '../../core/brief.service';
import { formatCount, formatPct } from '../../core/format';
import { InsightPacket } from '../../core/insight.model';
import { ShellService } from '../../core/shell.service';
import { TenantService } from '../../core/tenant.service';

interface VendorRow {
  vendorId: string;
  /** Worst single contribution this vendor carries on any insight. */
  worstPct: number;
  trips: number;
  findings: number;
  topInsightId: string;
  topHeadline: string;
}

/**
 * Vendors ranked by the share of findings they carry. Derived entirely from
 * attribution rows whose dim is a vendor -- there is no vendor endpoint, and
 * inventing one would mean showing vendors the detectors never implicated.
 */
@Component({
  selector: 'app-vendors-page',
  standalone: true,
  templateUrl: './vendors-page.component.html',
  styleUrl: './vendors-page.component.css',
})
export class VendorsPageComponent {
  private readonly briefService = inject(BriefService);
  private readonly router = inject(Router);
  private readonly shell = inject(ShellService);
  private readonly tenants = inject(TenantService);

  readonly insights = signal<InsightPacket[]>([]);
  readonly error = signal<string | null>(null);
  readonly loading = signal(false);

  readonly rows = computed<VendorRow[]>(() => {
    const byVendor = new Map<string, VendorRow>();
    for (const insight of this.insights()) {
      for (const item of insight.attribution) {
        if (!item.dim.includes('vendor')) {
          continue;
        }
        const held = byVendor.get(item.value);
        if (!held) {
          byVendor.set(item.value, {
            vendorId: item.value,
            worstPct: item.contribution_pct,
            trips: item.n,
            findings: 1,
            topInsightId: insight.insight_id,
            topHeadline: insight.narrative.headline,
          });
          continue;
        }
        held.findings += 1;
        held.trips += item.n;
        if (item.contribution_pct > held.worstPct) {
          held.worstPct = item.contribution_pct;
          held.topInsightId = insight.insight_id;
          held.topHeadline = insight.narrative.headline;
        }
      }
    }
    return [...byVendor.values()].sort((a, b) => b.worstPct - a.worstPct);
  });

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

  open(row: VendorRow): void {
    this.shell.requestInsight(row.topInsightId);
    this.router.navigateByUrl('/brief');
  }

  count(value: number): string {
    return formatCount(value);
  }

  pct(value: number): string {
    return formatPct(value);
  }

  private load(): void {
    this.loading.set(true);
    this.shell.loading.set(true);
    this.briefService.getBrief('ops').subscribe({
      next: (brief) => {
        this.insights.set(brief.insights);
        this.shell.insights.set(brief.insights);
        this.error.set(null);
        this.loading.set(false);
        this.shell.loading.set(false);
      },
      error: (err) => {
        this.insights.set([]);
        this.error.set(err?.message ?? 'The backend is unreachable.');
        this.loading.set(false);
        this.shell.loading.set(false);
      },
    });
  }
}
