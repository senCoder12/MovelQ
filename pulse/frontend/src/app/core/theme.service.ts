import { DOCUMENT } from '@angular/common';
import { Injectable, computed, effect, inject, signal } from '@angular/core';

/** Light, dark, or follow the operating system. */
export type ThemeMode = 'light' | 'dark' | 'system';

export const THEME_MODES: readonly ThemeMode[] = ['light', 'dark', 'system'];

/** Shared with the pre-paint script in index.html -- keep the two in sync. */
const STORAGE_KEY = 'pulse.theme';

const DARK_QUERY = '(prefers-color-scheme: dark)';

/** The token tokens.scss exposes for the browser-chrome colour. */
const THEME_COLOR_PROPERTY = '--pulse-theme-color';

/**
 * Owns the theme. Stamps `data-theme` on <html> for 'light' and 'dark', and
 * removes the attribute for 'system' so tokens.scss falls through to its
 * `prefers-color-scheme` block. All colour lives in tokens.scss -- this service
 * only decides which of its three states is active.
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly document = inject(DOCUMENT);
  private readonly query = this.document.defaultView?.matchMedia?.(DARK_QUERY);

  readonly modes = THEME_MODES;
  readonly mode = signal<ThemeMode>(restore());

  /**
   * What the OS is asking for right now. Written only from the media-query
   * listener, never from an effect -- see `resolved`.
   */
  private readonly systemDark = signal(this.query?.matches ?? false);

  /**
   * What is actually on screen once 'system' is resolved. Derived, not set:
   * Angular refuses signal writes inside an effect (NG0600), so computing this
   * is the only way it can stay in step with both `mode` and the OS.
   */
  readonly resolved = computed<'light' | 'dark'>(() => {
    const mode = this.mode();
    return mode === 'system' ? (this.systemDark() ? 'dark' : 'light') : mode;
  });

  constructor() {
    // Track the system flipping while we are on 'system'. Kept unconditional:
    // the signal records what the OS wants regardless of the current mode, so
    // switching back to 'system' later is already correct.
    this.query?.addEventListener?.('change', (event) => this.systemDark.set(event.matches));

    // The only side effect: reflect the choice onto the document. Writes no
    // signals, so it needs no allowSignalWrites.
    effect(() => {
      const mode = this.mode();
      const root = this.document.documentElement;
      if (mode === 'system') {
        root.removeAttribute('data-theme');
      } else {
        root.setAttribute('data-theme', mode);
      }
      this.applyThemeColor(mode);
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

  /**
   * index.html ships two media-scoped `theme-color` metas, which are right
   * while we follow the system. A browser uses the *first* matching one, so an
   * explicit choice is expressed by prepending a media-less meta that always
   * matches -- and removing it again on the way back to 'system'.
   */
  private applyThemeColor(mode: ThemeMode): void {
    const head = this.document.head;
    let override = head.querySelector<HTMLMetaElement>('meta[name="theme-color"][data-pulse]');

    if (mode === 'system') {
      override?.remove();
      return;
    }

    // Read back rather than hardcode: tokens.scss is the only place a raw
    // colour is allowed to live, and data-theme is already on <html> by now, so
    // the computed value is the palette we just switched to.
    const view = this.document.defaultView;
    const color = view
      ?.getComputedStyle(this.document.documentElement)
      .getPropertyValue(THEME_COLOR_PROPERTY)
      .trim();
    if (!color) {
      return;
    }

    if (!override) {
      override = this.document.createElement('meta');
      override.setAttribute('name', 'theme-color');
      override.setAttribute('data-pulse', '');
      head.insertBefore(override, head.firstChild);
    }
    override.setAttribute('content', color);
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
