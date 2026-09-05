// Mirrors contracts/openapi.yaml components.schemas.LeadershipPack 1:1.

export type Direction = 'good' | 'bad' | 'neutral';

export interface DateRange {
  from: string;
  to: string;
}

export interface LeadershipScope {
  tenant: string | null;
  sites: string[];
  trip_count: number;
  date_range: DateRange;
}

export interface LeadershipTile {
  label: string;
  value: string;
  reference: string;
  direction: Direction;
}

export interface LeadershipFinding {
  title: string;
  severity: number;
  body: string;
  recommendation: string;
  insight_id: string;
}

export interface LeadershipFooter {
  computed_from_trips: number;
  excluded_trips: number;
  excluded_pct: number;
  exclusion_reasons: string[];
}

export interface LeadershipPack {
  period: string;
  scope: LeadershipScope;
  headline: string;
  summary: string;
  tiles: LeadershipTile[];
  findings: LeadershipFinding[];
  footer: LeadershipFooter;
}
