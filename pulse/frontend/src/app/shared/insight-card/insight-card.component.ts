import { Component, ElementRef, computed, inject, input, output } from '@angular/core';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzTooltipDirective } from 'ng-zorro-antd/tooltip';

import { InsightPacket, RecommendedAction } from '../../core/insight.model';
import {
  domainTag,
  exposureStat,
  factTiles,
  severityLabel,
  shapeOf,
  toneOf,
  windowLabel,
} from '../../core/insight-presentation';

/**
 * One InsightPacket as a decision card: domain, severity and window on the
 * eyebrow row, the finding as a title and one-line lede, the evidence as up to
 * three fact boxes, and the escalation number plus its call to action pinned in
 * a right rail. Anything a box has to shorten stays reachable on hover; the
 * full working -- trace, exclusions, validation -- is one click away in the
 * audit-log drawer.
 */
@Component({
  selector: 'app-insight-card',
  standalone: true,
  imports: [NzIconModule, NzTooltipDirective],
  templateUrl: './insight-card.component.html',
  styleUrl: './insight-card.component.css',
})
export class InsightCardComponent {
  private readonly element = inject(ElementRef<HTMLElement>);

  readonly insight = input.required<InsightPacket>();

  /** Set by the feed's j/k cursor. Draws the selection ring; does not focus. */
  readonly selected = input(false);

  /** Emits the insight_id when the caller asks to see the trace. */
  readonly showMath = output<string>();

  /** Emits the clicked recommended action. */
  readonly actionClicked = output<RecommendedAction>();

  readonly shape = computed(() => shapeOf(this.insight()));
  readonly tone = computed(() => toneOf(this.insight().severity));
  readonly severityText = computed(() => severityLabel(this.insight().severity));
  readonly tag = computed(() => domainTag(this.insight()));
  readonly window = computed(() => windowLabel(this.insight().metric.window));
  readonly exposure = computed(() => exposureStat(this.insight()));
  readonly tiles = computed(() => factTiles(this.insight(), this.exposure().covers));

  /** The action the card promotes to its primary button. */
  readonly primaryAction = computed<RecommendedAction | null>(
    () => this.insight().narrative.recommended_actions[0] ?? null,
  );

  requestTrace(): void {
    this.showMath.emit(this.insight().insight_id);
  }

  clickAction(action: RecommendedAction): void {
    this.actionClicked.emit(action);
  }

  /** Title, draft and rationale on hover, so the button can stay one word. */
  actionDetail(action: RecommendedAction): string {
    return [action.title, action.draft, action.rationale].filter(Boolean).join(' — ');
  }

  scrollIntoView(): void {
    this.element.nativeElement.scrollIntoView({ block: 'nearest' });
  }
}
