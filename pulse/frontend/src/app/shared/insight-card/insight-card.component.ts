import { Component, ElementRef, computed, inject, input, output } from '@angular/core';
import { Router } from '@angular/router';
import { NzIconModule } from 'ng-zorro-antd/icon';

import {
  ACTION_BUTTON_LABEL,
  ActionType,
  applicableActionTypes,
  decidedButtonLabel,
} from '../../core/actions.model';
import { ActionsStateService } from '../../core/actions-state.service';
import { AlertsStateService } from '../../core/alerts-state.service';
import { formatAlertTime } from '../../core/alerts.model';
import { InsightPacket } from '../../core/insight.model';
import {
  domainTag,
  exposureStat,
  factTiles,
  severityLabel,
  shapeOf,
  toneOf,
  windowLabel,
} from '../../core/insight-presentation';

interface ActionButton {
  type: ActionType;
  label: string;
  decidedLabel: string | null;
  rejected: boolean;
}

interface AlertChip {
  alertId: string;
  label: string;
  /** A repeat still awaiting acknowledgement reads muted -- see the spec's
   * "re-raised, unacknowledged 24h" wording. */
  isRepeatPending: boolean;
}

/**
 * One InsightPacket as a decision card: domain, severity and window on the
 * eyebrow row, the finding as a title and one-line lede, the evidence as up to
 * three fact boxes, and the escalation number plus one button per applicable
 * action type pinned in a right rail. A button stays visible after a human
 * decides it -- it just switches to a muted "... approved 14:32" state,
 * since that state change is the whole point of showing a human was in the
 * loop. Anything a box has to shorten stays reachable on hover; the full
 * working -- trace, exclusions, validation -- is one click away in the
 * audit-log drawer.
 */
@Component({
  selector: 'app-insight-card',
  standalone: true,
  imports: [NzIconModule],
  templateUrl: './insight-card.component.html',
  styleUrl: './insight-card.component.css',
})
export class InsightCardComponent {
  private readonly element = inject(ElementRef<HTMLElement>);
  private readonly router = inject(Router);
  private readonly actionsState = inject(ActionsStateService);
  private readonly alertsState = inject(AlertsStateService);

  readonly insight = input.required<InsightPacket>();

  /** Set by the feed's j/k cursor. Draws the selection ring; does not focus. */
  readonly selected = input(false);

  /** `${insight_id}::${type}` of the button currently awaiting a draft from
   * the agent, or null -- set by the page while POST .../actions is in
   * flight, so only the clicked button shows a pending state. */
  readonly pendingActionKey = input<string | null>(null);

  /** Emits the insight_id when the caller asks to see the trace. */
  readonly showMath = output<string>();

  /** Emits the action type the operator wants drafted for this insight. */
  readonly draftRequested = output<ActionType>();

  readonly shape = computed(() => shapeOf(this.insight()));
  readonly tone = computed(() => toneOf(this.insight().severity));
  readonly severityText = computed(() => severityLabel(this.insight().severity));
  readonly tag = computed(() => domainTag(this.insight()));
  readonly window = computed(() => windowLabel(this.insight().metric.window));
  readonly exposure = computed(() => exposureStat(this.insight()));
  readonly tiles = computed(() => factTiles(this.insight(), this.exposure().covers));

  readonly actionButtons = computed<ActionButton[]>(() => {
    const insight = this.insight();
    return applicableActionTypes(insight).map((type) => {
      const decided = this.actionsState.latest(insight.insight_id, type);
      return {
        type,
        label: ACTION_BUTTON_LABEL[type],
        decidedLabel: decided ? decidedButtonLabel(type, decided) : null,
        rejected: decided?.status === 'REJECTED',
      };
    });
  });

  /** The card's "alerted HH:mm" chip -- null when this insight has never
   * fired an alert, so the card renders with no chip at all rather than a
   * hollow placeholder. */
  readonly alertChip = computed<AlertChip | null>(() => {
    const alert = this.alertsState.latestForInsight(this.insight().insight_id);
    if (!alert) {
      return null;
    }
    const isRepeatPending = alert.repeat_of !== null && alert.status === 'NEW';
    return {
      alertId: alert.alert_id,
      label: isRepeatPending
        ? 're-raised, unacknowledged 24h'
        : `alerted ${formatAlertTime(alert.fired_at)}`,
      isRepeatPending,
    };
  });

  isPending(type: ActionType): boolean {
    return this.pendingActionKey() === `${this.insight().insight_id}::${type}`;
  }

  requestTrace(): void {
    this.showMath.emit(this.insight().insight_id);
  }

  openAlert(alertId: string): void {
    this.router.navigateByUrl(`/alerts?open=${alertId}`);
  }

  requestDraft(type: ActionType): void {
    this.draftRequested.emit(type);
  }

  scrollIntoView(): void {
    this.element.nativeElement.scrollIntoView({ block: 'nearest' });
  }
}
