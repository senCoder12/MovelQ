import { Injectable, signal } from '@angular/core';

import { ActionDraft, ActionType } from './actions.model';

function key(insightId: string, type: ActionType): string {
  return `${insightId}::${type}`;
}

/** The insight card's button state for every (insight, action type) pair --
 * an in-memory read model, not a source of truth. The backend's ActionDraft
 * rows remain authoritative; this exists so a card can render "approved" the
 * instant a decision comes back, and so a page load can seed the same state
 * from GET /api/insights/{id}/actions without every card re-fetching it. */
@Injectable({ providedIn: 'root' })
export class ActionsStateService {
  private readonly decided = signal<ReadonlyMap<string, ActionDraft>>(new Map());

  /** The most recently decided draft for this (insight, type), or null if
   * still undecided (or never drafted). */
  latest(insightId: string, type: ActionType): ActionDraft | null {
    return this.decided().get(key(insightId, type)) ?? null;
  }

  /** Record a draft's outcome if it was actually decided -- a DRAFTED (not
   * yet approved/rejected) draft is not tracked here, since the card has
   * nothing different to show for it. */
  record(draft: ActionDraft): void {
    if (draft.status === 'DRAFTED') {
      return;
    }
    const next = new Map(this.decided());
    next.set(key(draft.insight_id, draft.type), draft);
    this.decided.set(next);
  }

  /** Bulk-seed from a page load's GET /api/insights/{id}/actions calls, one
   * per visible insight -- keeps the "approved" button state across a
   * reload without a per-card network round trip. */
  seed(drafts: ActionDraft[]): void {
    if (drafts.length === 0) {
      return;
    }
    const next = new Map(this.decided());
    for (const draft of drafts) {
      if (draft.status === 'DRAFTED') {
        continue;
      }
      const existing = next.get(key(draft.insight_id, draft.type));
      if (!existing || new Date(draft.created_at) > new Date(existing.created_at)) {
        next.set(key(draft.insight_id, draft.type), draft);
      }
    }
    this.decided.set(next);
  }
}
