import { HomeData, ShiftReadiness, Situation, Decision, AskMoveResponse } from '../types';

const API_BASE = '/api/v1';

interface CacheEntry<T> {
  timestamp: number;
  data: T;
}

const clientCache = new Map<string, CacheEntry<any>>();
const CLIENT_CACHE_TTL_MS = 60 * 1000; // 60 seconds

export function clearClientCache() {
  clientCache.clear();
}

async function fetchJson<T>(url: string, options?: RequestInit, useCache: boolean = true): Promise<T> {
  const isGet = !options || !options.method || options.method === 'GET';

  if (isGet && useCache) {
    const cached = clientCache.get(url);
    if (cached && Date.now() - cached.timestamp < CLIENT_CACHE_TTL_MS) {
      return cached.data as T;
    }
  }

  const res = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  const data = await res.json();

  if (isGet && useCache) {
    clientCache.set(url, { timestamp: Date.now(), data });
  }

  return data;
}

export const api = {
  // Not cached: these two back the live dashboard views, which now poll
  // (see useFetch's intervalMs) specifically so a new alert shows up
  // without a manual reload. A cached response would defeat that.
  getHome: (bu?: string, date?: string) => fetchJson<HomeData>(`/home?business_unit=${bu || ''}&trip_date=${date || ''}`, undefined, false),
  getSituations: (bu?: string) => fetchJson<Situation[]>(`/situations?business_unit=${bu || ''}`, undefined, false),
  getShifts: (bu?: string, date?: string, vendor?: string) => fetchJson<ShiftReadiness[]>(`/shifts?business_unit=${bu || ''}&date=${date || ''}&vendor=${vendor || ''}`),
  getVendors: (bu?: string, date?: string) => fetchJson<string[]>(`/vendors?business_unit=${bu || ''}&date=${date || ''}`),
  getSituation: (id: string) => fetchJson<Situation>(`/situations/${id}`),
  getSituationEvidence: (id: string) => fetchJson<any>(`/situations/${id}/evidence`),
  getSituationDecisions: (id: string) => fetchJson<any>(`/situations/${id}/decisions`),
  getSituationEmployees: (id: string) => fetchJson<any[]>(`/situations/${id}/employees`),
  getDecisions: (bu?: string) => fetchJson<any[]>(`/decisions?business_unit=${bu || ''}`),
  takeAction: async (situationId: string, actionType: string) => {
    clearClientCache();
    return fetchJson<any>(`/situations/${situationId}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action_type: actionType })
    }, false);
  },
  resolveSituation: async (situationId: string) => {
    clearClientCache();
    return fetchJson<Situation>(`/situations/${situationId}/resolve`, {
      method: 'POST',
    }, false);
  },
  askMove: (question: string, context?: Record<string, any>) =>
    fetchJson<AskMoveResponse>('/ask', {
      method: 'POST',
      body: JSON.stringify({ question, context })
    }, false),
  simulateAlert: (alert_name: string, priority: 'HIGH' | 'LOW') =>
    fetchJson<{
      trip_id: number; event_id: string; event_type: string; priority: string;
      severity: string; situation_created: boolean; message: string;
    }>('/simulate-alert', {
      method: 'POST',
      body: JSON.stringify({ alert_name, priority }),
    }, false),
};
