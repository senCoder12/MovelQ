import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  BriefResponse,
  DataQualityResponse,
  InsightPacket,
  Persona,
  TraceResponse,
} from './insight.model';

@Injectable({ providedIn: 'root' })
export class BriefService {
  private readonly http = inject(HttpClient);

  getBrief(persona: Persona): Observable<BriefResponse> {
    const params = new HttpParams().set('persona', persona);
    return this.http.get<BriefResponse>('/api/brief', { params });
  }

  getInsight(id: string): Observable<InsightPacket> {
    return this.http.get<InsightPacket>(`/api/insights/${id}`);
  }

  getInsightTrace(id: string): Observable<TraceResponse> {
    return this.http.get<TraceResponse>(`/api/insights/${id}/trace`);
  }

  getDataQuality(): Observable<DataQualityResponse> {
    return this.http.get<DataQualityResponse>('/api/data-quality');
  }
}
