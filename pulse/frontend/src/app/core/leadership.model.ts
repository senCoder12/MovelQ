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

// --- Send flow: recipients, preview and dispatch ----------------------------
// Mirrors backend/.../report's dto records 1:1.

export type RecipientRole = 'transport_head' | 'finance' | 'vendor_manager' | 'leadership';

export interface ReportRecipient {
  recipient_id: string;
  name: string;
  email: string;
  role: RecipientRole;
  is_default: boolean;
}

export type DispatchTransport = 'logged' | 'smtp';

export interface RecipientsResponse {
  recipients: ReportRecipient[];
  transport: DispatchTransport;
}

export interface PreviewRequest {
  period: string;
  recipient_ids: string[];
}

export interface PreviewResponse {
  subject: string;
  body_html: string;
  body_text: string;
}

export interface DispatchApiRequest {
  period: string;
  recipient_ids: string[];
  subject?: string;
  note?: string;
}

export interface DispatchRecipient {
  recipient_id: string;
  name: string;
  email: string;
  role: RecipientRole;
}

export type DispatchStatus = 'SUCCESS' | 'FAILED';

export interface DispatchView {
  dispatch_id: string;
  report_id: string;
  period: string;
  recipients: DispatchRecipient[];
  subject: string;
  body_html: string;
  body_text: string;
  transport: DispatchTransport;
  status: DispatchStatus;
  dispatched_at: string;
  dispatched_by: string;
  provider_message_id: string | null;
  error_summary: string | null;
  content_hash: string;
}

export interface DispatchApiResponse {
  dispatch: DispatchView;
  duplicate: boolean;
}
