import { Component, computed, inject } from '@angular/core';
import { ThemeService } from '../theme.service';

/**
 * Switches the app between the dark and light palettes.
 *
 * Rendered as a checkbox-style switch rather than a plain button so assistive
 * tech announces the current state, not just the action: `role="switch"` plus
 * `aria-checked` reads as "Light theme, switch, off". The visible label is the
 * icon, so the accessible name comes from `aria-label`.
 *
 * Both icons are always in the DOM and cross-fade, which keeps the control's
 * width from twitching as the theme changes.
 */
@Component({
  selector: 'app-theme-toggle',
  standalone: true,
  host: { '[class.is-light]': 'isLight()' },
  template: `
    <button
      type="button"
      class="theme-toggle"
      role="switch"
      [attr.aria-checked]="isLight()"
      [attr.aria-label]="label()"
      [title]="label()"
      data-testid="theme-toggle"
      (click)="toggle()"
    >
      <span class="theme-toggle__icons" aria-hidden="true">
        <!-- Sun: shown in dark mode, where the action is "switch to light" -->
        <svg
          class="theme-toggle__icon theme-toggle__icon--sun"
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
        <!-- Moon: shown in light mode -->
        <svg
          class="theme-toggle__icon theme-toggle__icon--moon"
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
        </svg>
      </span>
    </button>
  `,
  styles: [
    `
      :host {
        display: inline-flex;
      }

      .theme-toggle {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 34px;
        height: 34px;
        padding: 0;
        border: 1px solid var(--line);
        border-radius: 50%;
        background: transparent;
        color: var(--muted);
        cursor: pointer;
        transition:
          color var(--transition-fast),
          border-color var(--transition-fast),
          background-color var(--transition-fast);
      }

      .theme-toggle:hover {
        color: var(--text);
        border-color: var(--ball);
        background-color: rgba(var(--tint-rgb), 0.06);
      }

      .theme-toggle:focus-visible {
        outline: 2px solid var(--ball);
        outline-offset: 2px;
      }

      /* One grid cell holds both icons so neither reserves extra width. */
      .theme-toggle__icons {
        display: grid;
        width: 18px;
        height: 18px;
      }

      .theme-toggle__icon {
        grid-area: 1 / 1;
        transition:
          opacity var(--transition-fast),
          transform var(--transition-fast);
      }

      .theme-toggle__icon--moon {
        opacity: 0;
        transform: rotate(-45deg) scale(0.6);
      }

      :host(.is-light) .theme-toggle__icon--sun {
        opacity: 0;
        transform: rotate(45deg) scale(0.6);
      }

      :host(.is-light) .theme-toggle__icon--moon {
        opacity: 1;
        transform: none;
      }

      @media (prefers-reduced-motion: reduce) {
        .theme-toggle,
        .theme-toggle__icon {
          transition: none;
        }
      }
    `,
  ],
})
export class ThemeToggleComponent {
  private themeService = inject(ThemeService);

  readonly isLight = computed(() => this.themeService.theme() === 'light');
  readonly label = computed(() =>
    this.isLight() ? 'Switch to dark theme' : 'Switch to light theme'
  );

  toggle() {
    this.themeService.toggleTheme();
  }
}
