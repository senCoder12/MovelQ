import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { NzAlertModule } from 'ng-zorro-antd/alert';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzListModule } from 'ng-zorro-antd/list';
import { NzPageHeaderModule } from 'ng-zorro-antd/page-header';
import { NzSpinModule } from 'ng-zorro-antd/spin';

import { HealthResponse } from '../../core/health.model';
import { HealthService } from '../../core/health.service';
import { StatusBadgeComponent } from '../../shared/status-badge.component';

@Component({
  selector: 'app-health-page',
  standalone: true,
  imports: [
    NzAlertModule,
    NzButtonModule,
    NzCardModule,
    NzIconModule,
    NzListModule,
    NzPageHeaderModule,
    NzSpinModule,
    StatusBadgeComponent,
  ],
  templateUrl: './health-page.component.html',
  styleUrl: './health-page.component.css',
})
export class HealthPageComponent implements OnInit {
  private readonly healthService = inject(HealthService);

  readonly health = signal<HealthResponse | null>(null);
  readonly error = signal<string | null>(null);
  readonly loading = signal(false);

  readonly backendMeta = computed(() => describe(this.health()?.service, this.health()?.version));
  readonly agentMeta = computed(() =>
    describe(this.health()?.agent?.service, this.health()?.agent?.version),
  );

  ngOnInit(): void {
    this.refresh();
  }

  refresh(): void {
    this.loading.set(true);
    this.error.set(null);
    this.healthService.getHealth().subscribe({
      next: (health) => {
        this.health.set(health);
        this.loading.set(false);
      },
      error: (err) => {
        this.health.set(null);
        this.error.set(err?.message ?? 'Unable to reach the backend');
        this.loading.set(false);
      },
    });
  }
}

function describe(service?: string | null, version?: string | null): string {
  if (!service) {
    return 'not reported';
  }
  return version ? `${service} · v${version}` : service;
}
