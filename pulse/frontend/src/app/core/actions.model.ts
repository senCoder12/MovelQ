// Mirrors backend/.../action/dto 1:1 -- the "act" third of sense-reason-act.
// The agent only ever produces a DRAFTED row; every other status is written
// by a human decision (POST /actions/{id}/approve|reject), never in bulk.

export type ActionType =
  | 'VENDOR_ESCALATION'
  | 'SYSTEM_AUDIT_REQUEST'
  | 'ESCORT_COVERAGE_REVIEW'
  | 'BILLING_RECONCILIATION';

export type ActionStatus = 'DRAFTED' | 'APPROVED' | 'REJECTED' | 'EDITED_APPROVED';

export type Confidence = 'high' | 'medium' | 'low';

export interface Recipient {
  role: string;
  name: string;
}

export interface FactCited {
  label: string;
  value: string;
  source_field: string;
}

export interface ActionPreview {
  what_changes: string;
  reversible: boolean;
}

export interface ApprovalDecision {
  decision: string;
  decided_by: string;
  decided_at: string;
  edited_subject: string | null;
  edited_body: string | null;
  note: string | null;
}

export interface ActionDraft {
  action_id: string;
  insight_id: string;
  type: ActionType;
  title: string;
  recipient: Recipient;
  channel: string;
  subject: string;
  body: string;
  facts_cited: FactCited[];
  preview: ActionPreview;
  rationale: string;
  confidence: Confidence;
  status: ActionStatus;
  created_at: string;
  decision: ApprovalDecision | null;
}

export interface ApproveRequest {
  note?: string;
  edited_subject?: string;
  edited_body?: string;
}

export interface RejectRequest {
  reason: string;
}

// --- Which buttons an insight card shows ------------------------------------
// Mirrors agent/app/actions/drafters.py:applicable_action_types exactly --
// the agent is the source of truth for whether a draft actually grounds
// (it re-checks and 400s otherwise); this only decides which buttons render.
// ESCORT_COVERAGE_REVIEW is deliberately exclusive of VENDOR_ESCALATION even
// though escort_coverage_night_female carries vendor attribution -- see the
// drafters.py module docstring for why.

const ESCORT_COVERAGE_METRIC = 'escort_coverage_night_female';
const BILLING_METRICS = new Set(['ev_contract_mismatch_rate', 'unbilled_km_rate']);
const DELAY_RECONCILIATION_METRIC = 'delay_reconciliation_gap';

export function applicableActionTypes(insight: {
  metric: { id: string };
  attribution: { dim: string }[];
}): ActionType[] {
  const metricId = insight.metric.id;
  if (metricId === ESCORT_COVERAGE_METRIC) {
    return ['ESCORT_COVERAGE_REVIEW'];
  }
  if (BILLING_METRICS.has(metricId)) {
    return ['BILLING_RECONCILIATION'];
  }

  const types: ActionType[] = [];
  if (insight.attribution.some((a) => a.dim === 'vendor_id')) {
    types.push('VENDOR_ESCALATION');
  }
  if (metricId === DELAY_RECONCILIATION_METRIC) {
    types.push('SYSTEM_AUDIT_REQUEST');
  }
  return types;
}

export const ACTION_BUTTON_LABEL: Record<ActionType, string> = {
  VENDOR_ESCALATION: 'Draft escalation',
  SYSTEM_AUDIT_REQUEST: 'Draft audit request',
  ESCORT_COVERAGE_REVIEW: 'Draft coverage review',
  BILLING_RECONCILIATION: 'Draft reconciliation',
};

export const ACTION_TYPE_LABEL: Record<ActionType, string> = {
  VENDOR_ESCALATION: 'Vendor escalation',
  SYSTEM_AUDIT_REQUEST: 'System audit request',
  ESCORT_COVERAGE_REVIEW: 'Escort coverage review',
  BILLING_RECONCILIATION: 'Billing reconciliation',
};

/** "Escalation approved 14:32" -- the muted state a card's button settles
 * into once a human has decided. Rejections read as a plain past tense; only
 * an approval (edited or not) gets the "approved" wording the design calls
 * out as the demo moment. */
export function decidedButtonLabel(type: ActionType, draft: ActionDraft): string {
  const noun = ACTION_BUTTON_LABEL[type].replace(/^Draft /, '');
  const time = draft.decision ? formatDecidedTime(draft.decision.decided_at) : '';
  if (draft.status === 'REJECTED') {
    return `${noun} rejected${time ? ' ' + time : ''}`;
  }
  return `${noun} approved${time ? ' ' + time : ''}`;
}

function formatDecidedTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false });
}
