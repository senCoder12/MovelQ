import { Component } from '@angular/core';

import { HealthPageComponent } from './features/health/health-page.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [HealthPageComponent],
  template: `<app-health-page />`,
})
export class AppComponent {}
