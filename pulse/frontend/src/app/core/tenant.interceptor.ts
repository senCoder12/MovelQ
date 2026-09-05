import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { TenantService } from './tenant.service';

/** Backend rejects any /api request without X-Tenant-Id. The header is read
 * fresh per request from TenantService, so switching tenants in the rail
 * re-scopes every subsequent call without touching the services. */
export const tenantInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith('/api')) {
    return next(req);
  }
  const tenantId = inject(TenantService).tenantId();
  return next(req.clone({ setHeaders: { 'X-Tenant-Id': tenantId } }));
};
