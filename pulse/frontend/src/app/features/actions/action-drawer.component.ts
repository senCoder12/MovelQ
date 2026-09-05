import { Component, computed, effect, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NzDrawerModule } from 'ng-zorro-antd/drawer';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzNotificationService } from 'ng-zorro-antd/notification';

import { ActionsService } from '../../core/actions.service';
import { ActionDraft, ACTION_TYPE_LABEL } from '../../core/actions.model';

/**
 * Review-and-approve drawer for one drafted action. Opened from an insight
 * card's "Draft ..." button once the agent has produced a draft; nothing
 * here ever sends anything -- Approve/Reject only write an ApprovalLog row
 * (see ActionDraftService's class docstring on the backend).
 *
 * Editing is local until Approve is pressed: `subject`/`body` are plain
 * signals seeded from the draft and never sent back except as
 * edited_subject/edited_body on approval, and only when they differ from
 * what the agent proposed -- the original draft is never overwritten.
 */
@Component({
  selector: 'app-action-drawer',
  standalone: true,
  imports: [NzDrawerModule, NzIconModule, FormsModule],
  templateUrl: './action-drawer.component.html',
  styleUrl: './action-drawer.component.css',
})
export class ActionDrawerComponent {
  private readonly actionsService = inject(ActionsService);
  private readonly notification = inject(NzNotificationService);

  readonly visible = input(false);
  readonly draft = input<ActionDraft | null>(null);

  readonly closed = output<void>();
  /** Emits the finalized draft (status APPROVED/REJECTED/EDITED_APPROVED)
   * once a decision is recorded -- the caller updates the card's button
   * state and the audit list from this. */
  readonly decided = output<ActionDraft>();

  readonly subject = signal('');
  readonly body = signal('');
  readonly rejecting = signal(false);
  readonly reason = signal('');
  readonly saving = signal(false);

  readonly typeLabel = computed(() => {
    const draft = this.draft();
    return draft ? ACTION_TYPE_LABEL[draft.type] : '';
  });

  readonly subjectEdited = computed(() => this.subject() !== (this.draft()?.subject ?? ''));
  readonly bodyEdited = computed(() => this.body() !== (this.draft()?.body ?? ''));
  readonly isEdited = computed(() => this.subjectEdited() || this.bodyEdited());
  readonly approveLabel = computed(() => (this.isEdited() ? 'Approve edited' : 'Approve'));

  constructor() {
    effect(
      () => {
        const draft = this.draft();
        this.subject.set(draft?.subject ?? '');
        this.body.set(draft?.body ?? '');
        this.rejecting.set(false);
        this.reason.set('');
        this.saving.set(false);
      },
      { allowSignalWrites: true },
    );
  }

  startReject(): void {
    this.rejecting.set(true);
  }

  cancelReject(): void {
    this.rejecting.set(false);
    this.reason.set('');
  }

  approve(): void {
    const draft = this.draft();
    if (!draft || this.saving()) {
      return;
    }
    this.saving.set(true);
    this.actionsService
      .approve(draft.action_id, {
        edited_subject: this.subjectEdited() ? this.subject() : undefined,
        edited_body: this.bodyEdited() ? this.body() : undefined,
      })
      .subscribe({
        next: (updated) => {
          this.saving.set(false);
          this.notification.success(
            this.isEdited() ? 'Edited action approved' : 'Action approved',
            updated.title,
          );
          this.decided.emit(updated);
          this.close();
        },
        error: (err) => {
          this.saving.set(false);
          this.notification.error('Unable to approve', err?.error?.message ?? err?.message ?? 'The backend is unreachable.');
        },
      });
  }

  confirmReject(): void {
    const draft = this.draft();
    const reason = this.reason().trim();
    if (!draft || !reason || this.saving()) {
      return;
    }
    this.saving.set(true);
    this.actionsService.reject(draft.action_id, { reason }).subscribe({
      next: (updated) => {
        this.saving.set(false);
        this.notification.info('Action rejected', updated.title);
        this.decided.emit(updated);
        this.close();
      },
      error: (err) => {
        this.saving.set(false);
        this.notification.error('Unable to reject', err?.error?.message ?? err?.message ?? 'The backend is unreachable.');
      },
    });
  }

  close(): void {
    this.closed.emit();
  }
}
