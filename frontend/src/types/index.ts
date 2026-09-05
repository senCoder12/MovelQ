export interface Trip {
  trip_id: number;
  // additional trip fields
}

export interface ShiftReadiness {
  office: string;
  shift: string;
  direction: string;
  business_unit: string;
  trip_date: string;
  employees_expected: number;
  employees_ready_on_time: number;
  employees_late: number;
  employees_noshow: number;
  employees_at_risk: number;
  readiness_score: number;
  historical_baseline: number | null;
  delta_pp: number | null;
  affected_trips: number;
  affected_routes: number;
  top_contributing_situation: string | null;
  on_time_rate: number | null;
  avg_delay_minutes: number | null;
  p90_delay_minutes: number | null;
  p95_delay_minutes: number | null;
}

export type SituationType = 'SHIFT_READINESS_RISK' | 'ROUTE_DISRUPTION' | 'VENDOR_RELIABILITY' | 'EMPLOYEE_IMPACT_CLUSTER' | 'SAFETY_SITUATION' | 'DATA_CONFIDENCE';
export type SituationStatus = 'DETECTED' | 'INVESTIGATING' | 'ACTION_RECOMMENDED' | 'ACTION_PENDING' | 'ACTIONED' | 'VERIFYING' | 'RESOLVED' | 'DISMISSED';
export type SituationPriority = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
export type ActionType = 'DO_NOTHING' | 'NOTIFY_EMPLOYEES' | 'ESCALATE_VENDOR' | 'SIMULATE_VEHICLE_REASSIGNMENT' | 'NODAL_CONVERSION';

export interface SituationImpact {
  affected_employees: number;
  affected_trips: number;
  affected_routes: number;
  delay_minutes_total: number;
  delay_p95: number | null;
  historical_delay_p95: number | null;
  readiness_delta_pp: number | null;
  cost_impact: number | null;
  noshow_count: number;
}

export interface Situation {
  situation_id: string;
  situation_type: SituationType;
  status: SituationStatus;
  priority: SituationPriority;
  title: string;
  description: string;
  business_unit: string;
  office: string | null;
  shift: string | null;
  direction: string | null;
  impact: SituationImpact;
  confidence: number;
  recommended_actions: string[];
  current_action: string | null;
  outcome: string | null;
  first_seen: string;
  last_seen: string;
  supporting_episode_ids: string[];
  historical_context: Record<string, any>;
}

export interface AlertEpisode {
  episode_id: string;
  business_unit: string;
  trip_id: number;
  event_type: string;
  source: string | null;
  first_seen: string;
  last_seen: string;
  occurrence_count: number;
  duration_minutes: number;
  state: string;
}

export interface ActionOption {
  action_type: ActionType;
  description: string;
  expected_impact: string;
  estimated_cost: string;
  confidence: string;
  supporting_evidence: string[];
  assumptions: string[];
}

export interface Decision {
  decision_id: string;
  situation_id: string;
  options: ActionOption[];
  recommended_action: ActionType | null;
  recommendation_reasoning: string;
}

export interface HomeData {
  readiness_summary: ShiftReadiness[];
  active_situations: Situation[];
  recent_actions: any[];
  stats: {
    total_trips: number;
    total_employees: number;
    active_situations: number;
    overall_readiness: number;
  };
}

export interface AskMoveResponse {
  answer: string;
  evidence: Record<string, any>;
  confidence: string;
}
