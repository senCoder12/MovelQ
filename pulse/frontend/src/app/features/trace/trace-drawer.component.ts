import { Component, effect, inject, input, output, signal } from '@angular/core';
import { NzDrawerModule } from 'ng-zorro-antd/drawer';
import { NzIconModule } from 'ng-zorro-antd/icon';

import { BriefService } from '../../core/brief.service';
import { InsightPacket, TraceEntry } from '../../core/insight.model';

/** Drill-down drawer opened from an insight card's "show the math". Shows the metric id,
 * its window, and per-query numerator/denominator counts, exclusions and a validation
 * block for every entry in GET /api/insights/{id}/trace. */
@Component({
  selector: 'app-trace-drawer',
  standalone: true,
  imports: [NzDrawerModule, NzIconModule],
  templateUrl: './trace-drawer.component.html',
  styleUrl: './trace-drawer.component.css',
})
export class TraceDrawerComponent {
  private readonly briefService = inject(BriefService);

  readonly visible = input(false);
  readonly insight = input<InsightPacket | null>(null);

  readonly closed = output<void>();

  readonly entries = signal<TraceEntry[] | null>(null);
  readonly loading = signal(false);
  readonly loadError = signal(false);

  constructor() {
    effect(
      () => {
        const insight = this.insight();
        if (!this.visible() || !insight) {
          return;
        }
        this.load(insight.insight_id);
      },
      { allowSignalWrites: true },
    );
  }

  private load(insightId: string): void {
    this.entries.set(null);
    this.loadError.set(false);
    this.loading.set(true);
    this.briefService.getInsightTrace(insightId).subscribe({
      next: (trace) => {
        this.entries.set(trace.trace);
        this.loading.set(false);
      },
      error: () => {
        this.loadError.set(true);
        this.loading.set(false);
      },
    });
  }

  close(): void {
    this.closed.emit();
  }

  formatParams(params: Record<string, unknown>): string {
    return JSON.stringify(params);
  }
}
