import { Component, input } from '@angular/core';

/**
 * Form-level message that isn't tied to a single field — e.g. "Email or password
 * is incorrect" on a login form, or a server-side rule violation. For
 * connection/server failures use ToastService instead.
 */
@Component({
  selector: 'app-form-banner',
  standalone: true,
  template: `
    @if (message()) {
      <div
        class="form-banner"
        [class.form-banner--success]="kind() === 'success'"
        [attr.role]="kind() === 'success' ? 'status' : 'alert'"
        [attr.aria-live]="kind() === 'success' ? 'polite' : 'assertive'"
      >
        @if (kind() === 'success') {
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
            <path d="M20 6 9 17l-5-5" />
          </svg>
        } @else {
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        }
        <span>{{ message() }}</span>
      </div>
    }
  `,
})
export class FormBannerComponent {
  message = input<string | null>(null);
  kind = input<'error' | 'success'>('error');
}
