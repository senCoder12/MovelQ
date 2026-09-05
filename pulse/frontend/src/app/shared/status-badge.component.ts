import { Component, computed, input } from '@angular/core';
import { NzBadgeModule } from 'ng-zorro-antd/badge';

type NzStatus = 'success' | 'error' | 'default';

/** Renders a service status string as an ng-zorro status badge. */
@Component({
  selector: 'app-status-badge',
  standalone: true,
  imports: [NzBadgeModule],
  template: `<nz-badge [nzStatus]="nzStatus()" [nzText]="status()" />`,
})
export class StatusBadgeComponent {
  readonly status = input.required<string>();

  readonly nzStatus = computed<NzStatus>(() => {
    switch (this.status()) {
      case 'UP':
        return 'success';
      case 'DOWN':
        return 'error';
      default:
        return 'default';
    }
  });
}
