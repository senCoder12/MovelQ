import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ScanRunView } from './jobs.model';

@Injectable({ providedIn: 'root' })
export class JobsService {
  private readonly http = inject(HttpClient);

  /** Last 10 scan_run rows for the current tenant, newest first. */
  getStatus(): Observable<ScanRunView[]> {
    return this.http.get<ScanRunView[]>('/api/jobs/status');
  }

  /** Manual re-trigger -- not a scheduler, see ScanService's docstring. */
  triggerScan(): Observable<ScanRunView> {
    return this.http.post<ScanRunView>('/api/jobs/scan', {});
  }
}
