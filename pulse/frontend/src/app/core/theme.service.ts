import { DOCUMENT } from '@angular/common';
import { Injectable, effect, inject, signal } from '@angular/core';

/** Light, dark, or follow the operating system. */
export type ThemeMode = 'light' | 'dark' | 'system';

export const THEME_MODES: readonly ThemeMode[] = ['light', 'dark', 'system'];

const STORAGE_KEY = 'pulse.theme';

/**
 * Owns the theme. Stamps `data-theme` on <html> for 'light' and 'dark', and
 * removes the attribute for 'system' so tokens.scss falls through to its
 * `prefers-color-scheme` block. All colour lives in tokens.scss -- this service
 * only decides which of its three states is active.
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly document = inject(DOCUMENT);

  readonly modes = THEME_MODES;
  readonly mode = signal<ThemeMode>(restore());

  /** What is actually on screen once 'system' is resolved. */
  readonly resolved = signal<'light' | 'dark'>('light');

  constructor() {
    const query = this.document.defaultView?.matchMedia?.('(prefers-color-scheme: dark)');

    effect(() => {
      const mode = this.mode();
      const root = this.document.documentElement;
      if (mode === 'system') {
        root.removeAttribute('data-theme');
      } else {
        root.setAttribute('data-theme', mode);
      }
      this.resolved.set(mode === 'system' ? (query?.matches ? 'dark' : 'light') : mode);
    });

    // Track the system flipping while we are on 'system'.
    query?.addEventListener?.('change', (event) => {
      if (this.mode() === 'system') {
        this.resolved.set(event.matches ? 'dark' : 'light');
      }
    });
  }

  set(mode: ThemeMode): void {
    this.mode.set(mode);
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      // Storage disabled: the choice still applies for this session.
    }
  }

  /** Top-bar toggle: flips between light and dark, taking 'system' to its opposite. */
  toggle(): void {
    this.set(this.resolved() === 'dark' ? 'light' : 'dark');
  }
}

function restore(): ThemeMode {
  let stored: string | null = null;
  try {
    stored = localStorage.getItem(STORAGE_KEY);
  } catch {
    stored = null;
  }
  return (THEME_MODES as readonly string[]).includes(stored ?? '') ? (stored as ThemeMode) : 'system';
}
