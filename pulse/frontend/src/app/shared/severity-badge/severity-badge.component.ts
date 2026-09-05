import { Component, computed, input } from '@angular/core';

type SeverityBand = 'low' | 'medium' | 'high';

/** Renders a 0-100 severity score as a pill, colored via the three-stop severity ramp. */
@Component({
  selector: 'app-severity-badge',
  standalone: true,
  template: `
    <span class="severity-badge" [class]="'severity-badge--' + band()">
      {{ severity() }}
    </span>
  `,
  styleUrl: './severity-badge.component.css',
})
export class SeverityBadgeComponent {
  readonly severity = input.required<number>();

  readonly band = computed<SeverityBand>(() => {
    const value = this.severity();
    if (value >= 80) {
      return 'high';
    }
    if (value >= 50) {
      return 'medium';
    }
    return 'low';
  });
}
