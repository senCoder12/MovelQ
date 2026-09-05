// Mirrors backend/.../alert/dto 1:1 -- proactive alerting: who gets told,
// when, and how loudly, without anyone opening the app.

export type AlertStatus = 'NEW' | 'ACKNOWLEDGED' | 'MUTED' | 'EXPIRED';
export type Persona = 'ops' | 'strategic' | 'shift';
export type Urgency = 'immediate' | 'daily' | 'weekly';
export type Channel = 'in_app' | 'email_digest' | 'shift_handover';

export interface AlertView {
  alert_id: string;
  rule_id: string;
  insight_id: string;
  persona: Persona;
  urgency: Urgency;
  channel: Channel;
  entity_dim: string;
  entity_value: string;
  fired_at: string;
  scan_run_id: string;
  status: AlertStatus;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  acknowledged_note: string | null;
  repeat_of: string | null;
}

export interface PersonaRecipient {
  persona: Persona;
  name: string;
  email: string;
}

export interface AlertDeliveryView {
  delivery_id: string;
  alert_id: string;
  channel: Channel;
  rendered_subject: string;
  rendered_body: string;
  would_send_to: PersonaRecipient[];
  created_at: string;
  delivery_status: 'LOGGED';
}

export interface AcknowledgeRequest {
  note?: string;
}

export interface MuteRequest {
  reason: string;
  days: number;
}

/** "05:12" -- the insight-card chip and the alerts table both read this off
 * fired_at, in the reader's local time. */
export function formatAlertTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false });
}
