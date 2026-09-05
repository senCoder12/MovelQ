// Mirrors contracts/insight.schema.json 1:1. Field names/types match the
// schema exactly -- no speculative fields.

export interface Metric {
  id: string;
  name: string;
  value: number;
  unit: string;
  n: number;
  window: string;
}

export interface Entity {
  dim: string;
  id: string;
  name: string;
}

export type ReferenceType = 'historical' | 'sla' | 'peer' | 'industry' | 'computed';
export type ReferenceUnit = 'percent' | 'minutes' | 'inr' | 'count' | 'text';

export interface Reference {
  type: ReferenceType;
  label: string;
  value: number | string;
  unit: ReferenceUnit;
}

export interface Attribution {
  dim: string;
  value: string;
  contribution_pct: number;
  n: number;
}

export interface Control {
  control: string;
  gap_pp: number;
  survives: boolean;
}

export interface CoincidentEvent {
  type: string;
  date: string;
  note: string;
}

export interface Impact {
  affected_trips?: number;
  late_minutes_total?: number;
  cost_inr_month?: number;
}

export type Confidence = 'high' | 'medium' | 'low';

export interface DataQuality {
  excluded_pct: number;
  confidence: Confidence;
}

export type ValidationStatus = 'pass' | 'warn' | 'fail';

export interface Validation {
  status: ValidationStatus;
  notes: string;
}

export interface TraceEntry {
  query_id: string;
  params: Record<string, unknown>;
  numerator: number;
  denominator: number;
  exclusions: string[];
  validation: Validation;
}

export interface RecommendedAction {
  type: string;
  title: string;
  draft: string;
  rationale: string;
}

export interface Narrative {
  headline: string;
  body: string;
  recommended_actions: RecommendedAction[];
}

export interface InsightPacket {
  insight_id: string;
  metric: Metric;
  entity: Entity;
  references: Reference[];
  attribution: Attribution[];
  controls: Control[];
  coincident_events: CoincidentEvent[];
  impact: Impact;
  data_quality: DataQuality;
  severity: number;
  trace: TraceEntry[];
  narrative: Narrative;
}

// --- API response envelopes (contracts/openapi.yaml) ---

export type Persona = 'ops' | 'strategic' | 'shift';

export interface BriefResponse {
  persona: Persona;
  generated_at: string;
  insights: InsightPacket[];
}

export interface TraceResponse {
  insight_id: string;
  trace: TraceEntry[];
}

export interface DataQualityEntry {
  insight_id: string;
  metric_id: string;
  data_quality: DataQuality;
}

export interface DataQualityResponse {
  entries: DataQualityEntry[];
}
