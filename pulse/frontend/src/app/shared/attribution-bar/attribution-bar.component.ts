import { Component, computed, input } from '@angular/core';

import { Attribution } from '../../core/insight.model';

const SEGMENT_COLOR_VARS = ['var(--pulse-cat-1)', 'var(--pulse-cat-2)', 'var(--pulse-cat-3)'];
const MAX_NAMED_SEGMENTS = 3;
const N_FORMAT = new Intl.NumberFormat('en-US');

interface AttributionSegment extends Attribution {
  /** Display width, as a percent of the bar. Scaled down if raw contribution_pct values overlap/sum past 100. */
  widthPct: number;
  color: string;
}

/** Horizontal stacked bar of attribution contributions, plus a value/pct/n legend. Top 3
 * contributors get a named segment; everything past that collapses into one "everything
 * else" segment/legend row alongside the true unattributed remainder. */
@Component({
  selector: 'app-attribution-bar',
  standalone: true,
  template: `
    <div class="attribution-bar">
      @for (segment of segments(); track segment.dim + segment.value) {
        <span
          class="attribution-bar__segment"
          [style.width.%]="segment.widthPct"
          [style.background]="segment.color"
        ></span>
      }
      @if (fillerPct() > 0) {
        <span class="attribution-bar__segment attribution-bar__segment--filler" [style.width.%]="fillerPct()"></span>
      }
    </div>
    <ul class="attribution-legend">
      @for (segment of segments(); track segment.dim + segment.value) {
        <li class="attribution-legend__item">
          <span class="attribution-legend__swatch" [style.background]="segment.color"></span>
          <span class="attribution-legend__text">
            '{{ segment.value }}' {{ segment.contribution_pct }}% (n={{ formattedN(segment.n) }})
          </span>
        </li>
      }
      @if (fillerPct() > 0) {
        <li class="attribution-legend__item">
          <span class="attribution-legend__swatch attribution-legend__swatch--filler"></span>
          <span class="attribution-legend__text">everything else &middot; {{ fillerPct() }}%</span>
        </li>
      }
    </ul>
  `,
  styleUrl: './attribution-bar.component.css',
})
export class AttributionBarComponent {
  readonly attribution = input.required<Attribution[]>();

  private readonly ranked = computed(() =>
    [...this.attribution()].sort((a, b) => b.contribution_pct - a.contribution_pct),
  );

  private readonly named = computed(() => this.ranked().slice(0, MAX_NAMED_SEGMENTS));

  private readonly namedTotalPct = computed(() => this.named().reduce((total, item) => total + item.contribution_pct, 0));

  /** Scale factor keeping the bar's total visual width at or below 100%. */
  private readonly scale = computed(() => {
    const total = this.namedTotalPct();
    return total > 100 ? 100 / total : 1;
  });

  readonly segments = computed<AttributionSegment[]>(() =>
    this.named().map((item, index) => ({
      ...item,
      widthPct: item.contribution_pct * this.scale(),
      color: SEGMENT_COLOR_VARS[index % SEGMENT_COLOR_VARS.length],
    })),
  );

  readonly fillerPct = computed(() => Math.max(0, 100 - this.namedTotalPct() * this.scale()));

  formattedN(n: number): string {
    return N_FORMAT.format(n);
  }
}
