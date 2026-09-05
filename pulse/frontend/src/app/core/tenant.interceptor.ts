import { HttpInterceptorFn } from '@angular/common/http';

/** Backend rejects any /api request without X-Tenant-Id. No tenant switcher yet, so
 * every request is scoped to the 'catalyst' tenant. */
export const tenantInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith('/api')) {
    return next(req);
  }
  return next(req.clone({ setHeaders: { 'X-Tenant-Id': 'catalyst' } }));
};
