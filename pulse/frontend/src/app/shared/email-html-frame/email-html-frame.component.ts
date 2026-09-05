import { Component, computed, inject, input } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

/**
 * Renders a rendered-email HTML document exactly as it would appear in a
 * mail client -- inside a sandboxed iframe, not the page's own DOM, so
 * nothing in it (inline styles, table layout) is reinterpreted by Pulse's
 * own stylesheet. This is the same reason it is used both by the send
 * drawer's preview step and the history page's expanded row: "what they
 * would see" and "what was actually stored" have to be the same renderer.
 *
 * `sandbox=""` (no tokens) is deliberate -- no scripts, no same-origin, no
 * forms, no popups. The HTML is Pulse's own (LeadershipPackRenderer), never
 * third-party content, but the sandbox costs nothing and this is exactly
 * the kind of content a sandbox exists for.
 */
@Component({
  selector: 'app-email-html-frame',
  standalone: true,
  template: `
    <iframe
      class="email-html-frame"
      [style.width.px]="width()"
      [style.height.px]="height()"
      [srcdoc]="trustedHtml()"
      sandbox=""
      title="Rendered email preview"
    ></iframe>
  `,
  styleUrl: './email-html-frame.component.css',
})
export class EmailHtmlFrameComponent {
  private readonly sanitizer = inject(DomSanitizer);

  readonly html = input.required<string>();
  readonly width = input(600);
  readonly height = input(480);

  readonly trustedHtml = computed<SafeHtml>(() => this.sanitizer.bypassSecurityTrustHtml(this.html()));
}
