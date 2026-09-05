import { Component, computed, input } from '@angular/core';

import { Impact } from '../../core/insight.model';

interface ImpactTile {
  label: string;
  value: string;
}

const NUMBER_FORMAT = new Intl.NumberFormat('en-IN');

/** Unbordered metric tiles for present impact fields only. Deliberately unbordered, unlike reference-chips/control-chips. */
@Component({
  selector: 'app-impact-tiles',
  standalone: true,
  template: `
    <div class="impact-tiles">
      @for (tile of tiles(); track tile.label) {
        <div class="impact-tile">
          <span class="impact-tile__value">{{ tile.value }}</span>
          <span class="impact-tile__label">{{ tile.label }}</span>
        </div>
      }
    </div>
  `,
  styleUrl: './impact-tiles.component.css',
})
export class ImpactTilesComponent {
  readonly impact = input.required<Impact>();

  readonly tiles = computed<ImpactTile[]>(() => {
    const impact = this.impact();
    const tiles: ImpactTile[] = [];

    if (impact.affected_trips !== undefined) {
      tiles.push({ label: 'Affected trips', value: NUMBER_FORMAT.format(impact.affected_trips) });
    }
    if (impact.late_minutes_total !== undefined) {
      tiles.push({
        label: 'Late minutes (total)',
        value: `${NUMBER_FORMAT.format(impact.late_minutes_total)} min`,
      });
    }
    if (impact.cost_inr_month !== undefined) {
      tiles.push({
        label: 'Cost impact',
        value: `₹${NUMBER_FORMAT.format(impact.cost_inr_month)}/mo`,
      });
    }
    return tiles;
  });
}
