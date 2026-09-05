import { Component } from '@angular/core';

import { BriefPageComponent } from './features/brief/brief-page.component';
import { HealthPageComponent } from './features/health/health-page.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [HealthPageComponent, BriefPageComponent],
  template: `
    <app-health-page />
    <app-brief-page />
  `,
})
export class AppComponent {}
