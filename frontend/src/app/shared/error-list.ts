import { Component, input } from '@angular/core';

/**
 * A plain "please fix these" box for forms whose rules aren't expressed as
 * template-driven validators (cross-field checks, custom logic). The parent
 * computes the message list; this just renders it accessibly.
 */
@Component({
  selector: 'app-error-list',
  standalone: true,
  template: `
    @if (errors().length) {
      <div class="form-summary" role="alert" aria-live="assertive">
        <p class="form-summary__title">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          {{ title() }}
        </p>
        <ul class="form-summary__list">
          @for (msg of errors(); track msg) {
            <li>{{ msg }}</li>
          }
        </ul>
      </div>
    }
  `,
})
export class ErrorListComponent {
  errors = input<string[]>([]);
  title = input<string>('Please fix the following before continuing:');
}
