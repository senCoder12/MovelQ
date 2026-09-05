import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { LeadershipPack } from './leadership.model';

@Injectable({ providedIn: 'root' })
export class LeadershipService {
  private readonly http = inject(HttpClient);

  getLeadershipPack(period: string): Observable<LeadershipPack> {
    const params = new HttpParams().set('period', period);
    return this.http.get<LeadershipPack>('/api/reports/leadership', { params });
  }
}
