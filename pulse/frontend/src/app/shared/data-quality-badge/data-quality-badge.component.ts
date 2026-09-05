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
      <span nz-icon nzType="eye"></span>
      {{ excludedPct() }}% excluded &middot; confidence {{ dataQuality().confidence }}
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
