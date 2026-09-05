import { Component, OnInit, inject, signal } from '@angular/core';
import { NzNotificationService } from 'ng-zorro-antd/notification';
import { NzSkeletonModule } from 'ng-zorro-antd/skeleton';

import { BriefService } from '../../core/brief.service';
import { InsightPacket, Persona, RecommendedAction } from '../../core/insight.model';
import { InsightCardComponent } from '../../shared/insight-card/insight-card.component';
import { TraceDrawerComponent } from '../trace/trace-drawer.component';

const PERSONAS: Persona[] = ['ops', 'strategic', 'shift'];

@Component({
  selector: 'app-brief-page',
  standalone: true,
  imports: [NzSkeletonModule, InsightCardComponent, TraceDrawerComponent],
  templateUrl: './brief-page.component.html',
  styleUrl: './brief-page.component.css',
})
export class BriefPageComponent implements OnInit {
  private readonly briefService = inject(BriefService);
  private readonly notification = inject(NzNotificationService);

  readonly personas = PERSONAS;
  readonly persona = signal<Persona>('ops');
  readonly insights = signal<InsightPacket[] | null>(null);
  readonly loading = signal(false);
  readonly generatedAt = signal<string | null>(null);
  readonly scannedTrips = signal(0);

  readonly drawerVisible = signal(false);
  readonly traceInsight = signal<InsightPacket | null>(null);

  ngOnInit(): void {
    this.refresh();
  }

  selectPersona(persona: Persona): void {
    if (persona === this.persona()) {
      return;
    }
    this.persona.set(persona);
    this.refresh();
  }

  refresh(): void {
    this.loading.set(true);
    this.briefService.getBrief(this.persona()).subscribe({
      next: (brief) => {
        this.insights.set(brief.insights);
        this.generatedAt.set(brief.generated_at);
        this.scannedTrips.set(brief.insights.reduce((max, insight) => Math.max(max, insight.metric.n), 0));
        this.loading.set(false);
      },
      error: (err) => {
        this.insights.set(null);
        this.loading.set(false);
        this.notification.error(
          'Unable to load brief',
          err?.message ?? 'The backend is unreachable.',
        );
      },
    });
  }

  openTrace(insightId: string): void {
    const insight = this.insights()?.find((candidate) => candidate.insight_id === insightId) ?? null;
    this.traceInsight.set(insight);
    this.drawerVisible.set(true);
  }

  closeDrawer(): void {
    this.drawerVisible.set(false);
  }

  onActionClicked(action: RecommendedAction): void {
    this.notification.success(action.title, action.rationale);
  }
}
