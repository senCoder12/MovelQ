import { Component, computed, input } from '@angular/core';
import { NzIconModule } from 'ng-zorro-antd/icon';

import { DataQuality } from '../../core/insight.model';

/** Single muted line with an eye icon: "0% excluded · confidence high". */
@Component({
  selector: 'app-data-quality-badge',
  standalone: true,
  imports: [NzIconModule],
  template: `
    <span class="data-quality-badge">
      <span nz-icon nzType="eye" class="data-quality-badge__icon"></span>
      <span class="data-quality-badge__pct">{{ excludedPct() }}%</span> excluded &middot; confidence
      <span class="data-quality-badge__confidence">{{ dataQuality().confidence }}</span>
    </span>
  `,
  styleUrl: './data-quality-badge.component.css',
})
export class DataQualityBadgeComponent {
  readonly dataQuality = input.required<DataQuality>();

  readonly excludedPct = computed(() => {
    const value = this.dataQuality().excluded_pct;
    return Math.round(value * 10) / 10;
  });
}
