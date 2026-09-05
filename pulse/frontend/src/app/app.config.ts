import { ApplicationConfig, importProvidersFrom } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { registerLocaleData } from '@angular/common';
import en from '@angular/common/locales/en';
import { FormsModule } from '@angular/forms';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideRouter } from '@angular/router';
import { en_US, provideNzI18n } from 'ng-zorro-antd/i18n';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzNotificationModule } from 'ng-zorro-antd/notification';

import { routes } from './app.routes';
import { FixtureFleetSummarySource, FleetSummarySource } from './core/fleet-summary.source';
import { PULSE_ICONS } from './core/icons';
import { tenantInterceptor } from './core/tenant.interceptor';

registerLocaleData(en);

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    // The one place the insights page's non-packet figures are bound. Swap
    // FixtureFleetSummarySource for an HTTP implementation when the agent
    // exposes a daily-series / review-outcome endpoint.
    { provide: FleetSummarySource, useClass: FixtureFleetSummarySource },
    provideHttpClient(withInterceptors([tenantInterceptor])),
    provideAnimationsAsync(),
    provideNzI18n(en_US),
    importProvidersFrom(FormsModule),
    importProvidersFrom(NzIconModule.forRoot(PULSE_ICONS)),
    importProvidersFrom(NzNotificationModule),
  ],
};
