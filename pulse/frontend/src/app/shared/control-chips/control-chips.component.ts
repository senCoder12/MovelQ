import { Component, input } from '@angular/core';
import { NzIconModule } from 'ng-zorro-antd/icon';

import { Control } from '../../core/insight.model';

/** Pill per control, phrased from the fields: "survives {control} +{gap_pp}pp" (or "does not
 * survive"), tick icon shown only when the gap survives the control. */
@Component({
  selector: 'app-control-chips',
  standalone: true,
  imports: [NzIconModule],
  template: `
    <ul class="control-chips">
      @for (control of controls(); track control.control) {
        <li class="control-chip" [class.control-chip--fails]="!control.survives">
          @if (control.survives) {
            <span nz-icon nzType="check" class="control-chip__icon"></span>
          }
          <span class="control-chip__status">{{ control.survives ? 'survives' : 'does not survive' }}</span>
          <span class="control-chip__name">{{ control.control }}</span>
          <span class="control-chip__gap">{{ control.gap_pp > 0 ? '+' : '' }}{{ control.gap_pp }}pp</span>
        </li>
      }
    </ul>
  `,
  styleUrl: './control-chips.component.css',
})
export class ControlChipsComponent {
  readonly controls = input.required<Control[]>();
}
