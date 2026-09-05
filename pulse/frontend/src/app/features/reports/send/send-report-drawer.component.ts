import { Component, TemplateRef, ViewChild, computed, effect, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { NzDrawerModule } from 'ng-zorro-antd/drawer';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzNotificationService } from 'ng-zorro-antd/notification';

import {
  DispatchApiResponse,
  DispatchTransport,
  PreviewResponse,
  RecipientRole,
  ReportRecipient,
} from '../../../core/leadership.model';
import { LeadershipService } from '../../../core/leadership.service';
import { EmailHtmlFrameComponent } from '../../../shared/email-html-frame/email-html-frame.component';

interface RecipientGroup {
  role: RecipientRole;
  label: string;
  recipients: ReportRecipient[];
}

const ROLE_ORDER: RecipientRole[] = ['transport_head', 'leadership', 'finance', 'vendor_manager'];
const ROLE_LABEL: Record<RecipientRole, string> = {
  transport_head: 'Transport head',
  leadership: 'Leadership',
  finance: 'Finance',
  vendor_manager: 'Vendor manager',
};

/**
 * Three-step send flow for the leadership pack: who receives it, exactly
 * what they would see (rendered the same way the email would be, in a
 * sandboxed iframe -- not the on-screen pack), then a plain confirmation.
 * Nothing here ever calls a transport directly; POST .../dispatch does
 * that server-side, and the button here is only ever labelled honestly for
 * whichever transport is actually active (see `confirmLabel`).
 */
@Component({
  selector: 'app-send-report-drawer',
  standalone: true,
  imports: [NzDrawerModule, NzIconModule, FormsModule, EmailHtmlFrameComponent],
  templateUrl: './send-report-drawer.component.html',
  styleUrl: './send-report-drawer.component.css',
})
export class SendReportDrawerComponent {
  private readonly leadershipService = inject(LeadershipService);
  private readonly notification = inject(NzNotificationService);
  private readonly router = inject(Router);

  @ViewChild('duplicateTpl') private duplicateTpl?: TemplateRef<{}>;

  readonly visible = input(false);
  readonly period = input.required<string>();

  readonly closed = output<void>();
  readonly dispatched = output<DispatchApiResponse>();

  readonly step = signal<1 | 2 | 3>(1);

  readonly recipients = signal<ReportRecipient[]>([]);
  readonly recipientsLoading = signal(false);
  readonly transport = signal<DispatchTransport>('logged');
  readonly selectedIds = signal<ReadonlySet<string>>(new Set());
  readonly note = signal('');

  readonly preview = signal<PreviewResponse | null>(null);
  readonly previewLoading = signal(false);
  readonly previewError = signal<string | null>(null);
  readonly subject = signal('');
  readonly showPlainText = signal(false);

  readonly dispatching = signal(false);

  readonly groups = computed<RecipientGroup[]>(() => {
    const all = this.recipients();
    return ROLE_ORDER.map((role) => ({
      role,
      label: ROLE_LABEL[role],
      recipients: all.filter((r) => r.role === role),
    })).filter((group) => group.recipients.length > 0);
  });

  readonly selectedCount = computed(() => this.selectedIds().size);
  readonly canProceedFromStep1 = computed(() => this.selectedCount() > 0);
  readonly confirmLabel = computed(() => (this.transport() === 'smtp' ? 'Send' : 'Record dispatch'));

  readonly selectedRecipients = computed(() =>
    this.recipients().filter((r) => this.selectedIds().has(r.recipient_id)),
  );

  constructor() {
    effect(
      () => {
        if (this.visible()) {
          this.reset();
          this.loadRecipients();
        }
      },
      { allowSignalWrites: true },
    );
  }

  isSelected(recipientId: string): boolean {
    return this.selectedIds().has(recipientId);
  }

  toggleRecipient(recipientId: string): void {
    const next = new Set(this.selectedIds());
    if (next.has(recipientId)) {
      next.delete(recipientId);
    } else {
      next.add(recipientId);
    }
    this.selectedIds.set(next);
  }

  goToPreview(): void {
    if (!this.canProceedFromStep1()) {
      return;
    }
    this.step.set(2);
    if (!this.preview() && !this.previewLoading()) {
      this.fetchPreview();
    }
  }

  retryPreview(): void {
    this.fetchPreview();
  }

  backTo(step: 1 | 2): void {
    this.step.set(step);
  }

  goToConfirm(): void {
    this.step.set(3);
  }

  dispatch(): void {
    if (this.dispatching() || !this.canProceedFromStep1()) {
      return;
    }
    this.dispatching.set(true);
    const editedSubject = this.subject() !== (this.preview()?.subject ?? '') ? this.subject() : undefined;
    this.leadershipService
      .dispatch({
        period: this.period(),
        recipient_ids: [...this.selectedIds()],
        subject: editedSubject,
        note: this.note().trim() || undefined,
      })
      .subscribe({
        next: (response) => {
          this.dispatching.set(false);
          if (response.duplicate && this.duplicateTpl) {
            this.notification.template(this.duplicateTpl, { nzDuration: 10000 });
          } else {
            this.notification.success(
              this.transport() === 'smtp' ? 'Email sent' : 'Dispatch recorded',
              `${response.dispatch.recipients.length} recipient(s) · ${response.dispatch.period}`,
            );
          }
          this.dispatched.emit(response);
          this.close();
        },
        error: (err) => {
          this.dispatching.set(false);
          this.notification.error(
            'Unable to dispatch',
            err?.error?.message ?? err?.message ?? 'The backend is unreachable.',
          );
        },
      });
  }

  viewHistory(): void {
    this.router.navigateByUrl('/reports/history');
  }

  close(): void {
    this.closed.emit();
  }

  private reset(): void {
    this.step.set(1);
    this.selectedIds.set(new Set());
    this.note.set('');
    this.preview.set(null);
    this.previewError.set(null);
    this.subject.set('');
    this.showPlainText.set(false);
    this.dispatching.set(false);
  }

  private loadRecipients(): void {
    this.recipientsLoading.set(true);
    this.leadershipService.getRecipients().subscribe({
      next: (response) => {
        this.recipients.set(response.recipients);
        this.transport.set(response.transport);
        this.selectedIds.set(
          new Set(response.recipients.filter((r) => r.is_default).map((r) => r.recipient_id)),
        );
        this.recipientsLoading.set(false);
      },
      error: (err) => {
        this.recipientsLoading.set(false);
        this.notification.error('Unable to load recipients', err?.message ?? 'The backend is unreachable.');
      },
    });
  }

  private fetchPreview(): void {
    this.previewLoading.set(true);
    this.previewError.set(null);
    this.leadershipService
      .preview({ period: this.period(), recipient_ids: [...this.selectedIds()] })
      .subscribe({
        next: (response) => {
          this.preview.set(response);
          this.subject.set(response.subject);
          this.previewLoading.set(false);
        },
        error: (err) => {
          this.previewLoading.set(false);
          this.previewError.set(err?.message ?? 'The backend is unreachable.');
        },
      });
  }
}
