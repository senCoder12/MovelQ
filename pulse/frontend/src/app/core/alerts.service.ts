import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { AcknowledgeRequest, AlertDeliveryView, AlertStatus, AlertView, MuteRequest, Persona } from './alerts.model';

@Injectable({ providedIn: 'root' })
export class AlertsService {
  private readonly http = inject(HttpClient);

  list(status?: AlertStatus, persona?: Persona): Observable<AlertView[]> {
    let params = new HttpParams();
    if (status) {
      params = params.set('status', status);
    }
    if (persona) {
      params = params.set('persona', persona);
    }
    return this.http.get<AlertView[]>('/api/alerts', { params });
  }

  acknowledge(alertId: string, request: AcknowledgeRequest = {}): Observable<AlertView> {
    return this.http.post<AlertView>(`/api/alerts/${alertId}/acknowledge`, request);
  }

  mute(alertId: string, request: MuteRequest): Observable<AlertView> {
    return this.http.post<AlertView>(`/api/alerts/${alertId}/mute`, request);
  }

  getDelivery(alertId: string): Observable<AlertDeliveryView> {
    return this.http.get<AlertDeliveryView>(`/api/alerts/${alertId}/delivery`);
  }
}
