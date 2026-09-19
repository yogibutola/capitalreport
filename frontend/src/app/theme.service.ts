import { Injectable, PLATFORM_ID, inject, signal } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';

export type Theme = 'dark' | 'light';

/** Shared with the pre-hydration script in index.html — keep the two in step. */
export const THEME_STORAGE_KEY = 'sp-theme';

/** Dark is the original design, and the fallback whenever nothing else is known. */
export const DEFAULT_THEME: Theme = 'dark';

export function isTheme(value: unknown): value is Theme {
  return value === 'dark' || value === 'light';
}

/**
 * Owns the active colour theme. `App` mirrors the signal onto
 * `<html data-theme>`, which is what `styles.css` keys its palette off.
 *
 * Resolution order on first load: a theme the user has chosen before, else the
 * OS `prefers-color-scheme`, else dark. An explicit choice is sticky — once the
 * user has picked, the OS preference no longer overrides it.
 *
 * On the server there is no storage and no media query, so the theme resolves
 * to dark; `index.html` re-applies the stored choice before first paint so the
 * hydrated page does not flash.
 */
@Injectable({
  providedIn: 'root',
})
export class ThemeService {
  private platformId = inject(PLATFORM_ID);
  private readonly isBrowser = isPlatformBrowser(this.platformId);

  readonly theme = signal<Theme>(this.resolveInitialTheme());

  toggleTheme() {
    this.setTheme(this.theme() === 'dark' ? 'light' : 'dark');
  }

  setTheme(theme: Theme) {
    this.theme.set(theme);
    this.persist(theme);
  }

  private resolveInitialTheme(): Theme {
    if (!this.isBrowser) return DEFAULT_THEME;

    const stored = this.read();
    if (stored) return stored;

    // `matchMedia` is missing in some test environments, so guard rather than assume.
    const prefersLight =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-color-scheme: light)').matches;
    return prefersLight ? 'light' : DEFAULT_THEME;
  }

  /** Storage throws in Safari private mode and when cookies are blocked. */
  private read(): Theme | null {
    try {
      const stored = localStorage.getItem(THEME_STORAGE_KEY);
      return isTheme(stored) ? stored : null;
    } catch {
      return null;
    }
  }

  private persist(theme: Theme) {
    if (!this.isBrowser) return;
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // A non-persisted preference still applies for this session.
    }
  }
}
