import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  DispatchApiRequest,
  DispatchApiResponse,
  DispatchView,
  LeadershipPack,
  PreviewRequest,
  PreviewResponse,
  RecipientsResponse,
} from './leadership.model';

@Injectable({ providedIn: 'root' })
export class LeadershipService {
  private readonly http = inject(HttpClient);

  getLeadershipPack(period: string): Observable<LeadershipPack> {
    const params = new HttpParams().set('period', period);
    return this.http.get<LeadershipPack>('/api/reports/leadership', { params });
  }

  getRecipients(): Observable<RecipientsResponse> {
    return this.http.get<RecipientsResponse>('/api/reports/leadership/recipients');
  }

  preview(request: PreviewRequest): Observable<PreviewResponse> {
    return this.http.post<PreviewResponse>('/api/reports/leadership/preview', request);
  }

  dispatch(request: DispatchApiRequest): Observable<DispatchApiResponse> {
    return this.http.post<DispatchApiResponse>('/api/reports/leadership/dispatch', request);
  }

  getDispatchHistory(period?: string): Observable<DispatchView[]> {
    const params = period ? new HttpParams().set('period', period) : undefined;
    return this.http.get<DispatchView[]>('/api/reports/dispatches', { params });
  }
}
