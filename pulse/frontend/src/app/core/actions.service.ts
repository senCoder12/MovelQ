import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ActionDraft, ActionStatus, ActionType, ApproveRequest, RejectRequest } from './actions.model';

@Injectable({ providedIn: 'root' })
export class ActionsService {
  private readonly http = inject(HttpClient);

  listForInsight(insightId: string): Observable<ActionDraft[]> {
    return this.http.get<ActionDraft[]>(`/api/insights/${insightId}/actions`);
  }

  draft(insightId: string, type: ActionType): Observable<ActionDraft> {
    return this.http.post<ActionDraft>(`/api/insights/${insightId}/actions`, { type });
  }

  approve(actionId: string, request: ApproveRequest): Observable<ActionDraft> {
    return this.http.post<ActionDraft>(`/api/actions/${actionId}/approve`, request);
  }

  reject(actionId: string, request: RejectRequest): Observable<ActionDraft> {
    return this.http.post<ActionDraft>(`/api/actions/${actionId}/reject`, request);
  }

  audit(status?: ActionStatus): Observable<ActionDraft[]> {
    const params = status ? new HttpParams().set('status', status) : undefined;
    return this.http.get<ActionDraft[]>('/api/actions', { params });
  }
}
