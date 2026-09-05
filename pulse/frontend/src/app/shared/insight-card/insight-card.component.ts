import { Component, input, output } from '@angular/core';
import { NzIconModule } from 'ng-zorro-antd/icon';

import { InsightPacket, RecommendedAction } from '../../core/insight.model';
import { AttributionBarComponent } from '../attribution-bar/attribution-bar.component';
import { ControlChipsComponent } from '../control-chips/control-chips.component';
import { DataQualityBadgeComponent } from '../data-quality-badge/data-quality-badge.component';
import { ImpactTilesComponent } from '../impact-tiles/impact-tiles.component';
import { ReferenceChipsComponent } from '../reference-chips/reference-chips.component';
import { SeverityBadgeComponent } from '../severity-badge/severity-badge.component';

/** Full hand-written card for one InsightPacket -- composes every shared atom (plain markup, not
 * an ant card), in a fixed order: severity badge row, headline, reference chips, narrative body,
 * attribution bar, control chips, impact tiles, action buttons, data quality line. */
@Component({
  selector: 'app-insight-card',
  standalone: true,
  imports: [
    NzIconModule,
    SeverityBadgeComponent,
    ReferenceChipsComponent,
    AttributionBarComponent,
    ControlChipsComponent,
    ImpactTilesComponent,
    DataQualityBadgeComponent,
  ],
  templateUrl: './insight-card.component.html',
  styleUrl: './insight-card.component.css',
})
export class InsightCardComponent {
  readonly insight = input.required<InsightPacket>();

  /** Emits the insight_id when the caller clicks "show the math". */
  readonly showMath = output<string>();

  /** Emits the clicked recommended action. */
  readonly actionClicked = output<RecommendedAction>();

  requestTrace(): void {
    this.showMath.emit(this.insight().insight_id);
  }

  clickAction(action: RecommendedAction): void {
    this.actionClicked.emit(action);
  }
}
