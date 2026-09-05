import { Component, ElementRef, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzModalModule } from 'ng-zorro-antd/modal';

import { ShellService } from '../core/shell.service';
import { TENANTS, TenantService } from '../core/tenant.service';
import { NAV_ITEMS } from './nav';

type CommandGroup = 'Go to' | 'Tenant' | 'Insight';

interface Command {
  id: string;
  group: CommandGroup;
  label: string;
  /** Machine value shown right-aligned in the row, rendered monospace. */
  hint?: string;
  run: () => void;
}

/** ⌘K palette: jump to a view, switch tenant, or open an insight by headline.
 * Deliberately plain -- substring match over one flat command list, no fuzzy
 * ranking. Arrow keys move, Enter runs, Escape closes. */
@Component({
  selector: 'app-command-palette',
  standalone: true,
  imports: [NzModalModule, NzIconModule, FormsModule],
  templateUrl: './command-palette.component.html',
  styleUrl: './command-palette.component.css',
})
export class CommandPaletteComponent {
  private readonly router = inject(Router);
  private readonly tenants = inject(TenantService);

  readonly shell = inject(ShellService);

  @ViewChild('queryInput') queryInput?: ElementRef<HTMLInputElement>;

  readonly query = signal('');
  readonly selected = signal(0);

  private readonly commands = computed<Command[]>(() => [
    ...NAV_ITEMS.map((item) => ({
      id: `view:${item.path}`,
      group: 'Go to' as const,
      label: item.label,
      hint: item.path,
      run: () => this.router.navigateByUrl(item.path),
    })),
    ...TENANTS.map((tenant) => ({
      id: `tenant:${tenant}`,
      group: 'Tenant' as const,
      label: `Switch to ${tenant}`,
      hint: tenant,
      run: () => this.tenants.select(tenant),
    })),
    ...this.shell.insights().map((insight) => ({
      id: `insight:${insight.insight_id}`,
      group: 'Insight' as const,
      label: insight.narrative.headline,
      hint: insight.metric.id,
      run: () => {
        this.shell.requestInsight(insight.insight_id);
        this.router.navigateByUrl('/brief');
      },
    })),
  ]);

  readonly results = computed<Command[]>(() => {
    const query = this.query().trim().toLowerCase();
    if (!query) {
      return this.commands();
    }
    return this.commands().filter((command) =>
      `${command.label} ${command.hint ?? ''}`.toLowerCase().includes(query),
    );
  });

  /** True when this row starts a new group, so the template can print a divider label. */
  isGroupStart(index: number): boolean {
    const results = this.results();
    return index === 0 || results[index - 1].group !== results[index].group;
  }

  onQueryChange(value: string): void {
    this.query.set(value);
    this.selected.set(0);
  }

  onKeydown(event: KeyboardEvent): void {
    const count = this.results().length;
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        this.selected.set(count === 0 ? 0 : (this.selected() + 1) % count);
        break;
      case 'ArrowUp':
        event.preventDefault();
        this.selected.set(count === 0 ? 0 : (this.selected() - 1 + count) % count);
        break;
      case 'Enter':
        event.preventDefault();
        this.run(this.selected());
        break;
      case 'Escape':
        event.preventDefault();
        this.close();
        break;
      default:
        break;
    }
  }

  run(index: number): void {
    const command = this.results()[index];
    if (!command) {
      return;
    }
    command.run();
    this.close();
  }

  close(): void {
    this.shell.closePalette();
    this.query.set('');
    this.selected.set(0);
  }

  onOpened(): void {
    this.queryInput?.nativeElement.focus();
  }
}
