// Mirrors backend/.../job/ScanRunView 1:1 -- GET /api/jobs/status.

export type ScanRunStatus = 'SUCCESS' | 'FAILED' | 'PARTIAL';

export interface ScanRunView {
  scan_run_id: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  status: ScanRunStatus;
  insight_count: number;
  alerts_fired: number;
  alerts_suppressed: number;
  alerts_repeated: number;
  error_summary: string | null;
}
