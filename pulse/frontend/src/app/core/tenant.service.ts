import { Injectable, signal } from '@angular/core';

/** Tenants the operator can switch between. Every /api request is scoped to
 * exactly one of these via X-Tenant-Id -- the backend rejects requests without
 * the header, so there is no "all tenants" option. */
export const TENANTS = ['catalyst', 'orbit', 'pinnacle', 'vanta'] as const;

export type TenantId = (typeof TENANTS)[number];

const STORAGE_KEY = 'pulse.tenant';

/** Holds the current tenant. Read by tenantInterceptor for the outbound header
 * and by every view's reload effect, so selecting a tenant refetches the app. */
@Injectable({ providedIn: 'root' })
export class TenantService {
  readonly tenants = TENANTS;
  readonly tenantId = signal<TenantId>(restore());

  select(tenantId: TenantId): void {
    if (tenantId === this.tenantId()) {
      return;
    }
    this.tenantId.set(tenantId);
    try {
      localStorage.setItem(STORAGE_KEY, tenantId);
    } catch {
      // Private-mode / storage-disabled browsers: the selection still applies
      // for this session, it just does not survive a reload.
    }
  }
}

function restore(): TenantId {
  let stored: string | null = null;
  try {
    stored = localStorage.getItem(STORAGE_KEY);
  } catch {
    stored = null;
  }
  return (TENANTS as readonly string[]).includes(stored ?? '') ? (stored as TenantId) : TENANTS[0];
}
