import { Component, computed, input } from '@angular/core';

import { Impact, Metric } from '../../core/insight.model';
import { formatCount, formatInr } from '../../core/format';

interface Stat {
  /** The machine value -- always rendered monospace. */
  value: string;
  /** The word after it, in prose. Omitted for a stat that reads on its own. */
  label?: string;
}

/**
 * One inline row of impact numbers rather than a grid of tiles:
 * "1,17,605 trips · 54.5% rate · n=215,885". Same fields as before (only the
 * present ones render) plus the metric's own value and sample size, which
 * belong on the same line as the impact they explain.
 */
@Component({
  selector: 'app-impact-stats',
  standalone: true,
  template: `
    <div class="impact-stats">
      @for (stat of stats(); track stat.value + stat.label) {
        <span class="impact-stats__stat">
          <span class="impact-stats__value pulse-mono">{{ stat.value }}</span>
          @if (stat.label) {
            <span class="impact-stats__label">{{ stat.label }}</span>
          }
        </span>
      }
    </div>
  `,
  styleUrl: './impact-stats.component.css',
})
export class ImpactStatsComponent {
  readonly impact = input.required<Impact>();
  readonly metric = input<Metric | null>(null);

  readonly stats = computed<Stat[]>(() => {
    const impact = this.impact();
    const metric = this.metric();
    const stats: Stat[] = [];

    if (impact.affected_trips !== undefined) {
      stats.push({ value: formatCount(impact.affected_trips), label: 'trips' });
    }
    if (metric) {
      stats.push({ value: `${metric.value}${metric.unit}`, label: 'rate' });
    }
    if (impact.late_minutes_total !== undefined) {
      stats.push({ value: formatCount(impact.late_minutes_total), label: 'late min' });
    }
    if (impact.cost_inr_month !== undefined) {
      stats.push({ value: `${formatInr(impact.cost_inr_month)}/mo`, label: 'cost' });
    }
    if (metric) {
      stats.push({ value: `n=${formatCount(metric.n)}` });
    }
    return stats;
  });
}
