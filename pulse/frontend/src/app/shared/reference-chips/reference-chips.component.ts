import { Component, computed, input } from '@angular/core';

import { Reference } from '../../core/insight.model';

interface FormattedReference extends Reference {
  formattedValue: string;
}

const INR_FORMAT = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 });

/** Hairline chip per reference (historical/sla/peer/industry/computed), label + value
 * formatted by unit: percent -> "38.2%", minutes -> "9.87 min", inr -> "₹1,200".
 * Rendered inline on one row inside the insight card; the value is a machine
 * value and so renders monospace. */
function formatValue(reference: Reference): string {
  const value = reference.value;
  if (typeof value !== 'number') {
    return String(value);
  }
  switch (reference.unit) {
    case 'percent':
      return `${value}%`;
    case 'minutes':
      return `${value} min`;
    case 'inr':
      return `₹${INR_FORMAT.format(value)}`;
    default:
      return String(value);
  }
}

@Component({
  selector: 'app-reference-chips',
  standalone: true,
  template: `
    <ul class="reference-chips">
      @for (reference of formattedReferences(); track reference.label) {
        <li class="reference-chip" [class]="'reference-chip--' + reference.type">
          <span class="reference-chip__type">{{ reference.type }}</span>
          <span class="reference-chip__label">{{ reference.label }}</span>
          <span class="reference-chip__value">{{ reference.formattedValue }}</span>
        </li>
      }
    </ul>
  `,
  styleUrl: './reference-chips.component.css',
})
export class ReferenceChipsComponent {
  readonly references = input.required<Reference[]>();

  readonly formattedReferences = computed<FormattedReference[]>(() =>
    this.references().map((reference) => ({ ...reference, formattedValue: formatValue(reference) })),
  );
}
