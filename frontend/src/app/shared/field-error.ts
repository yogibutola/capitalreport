import { Component, input } from '@angular/core';
import { NgModel } from '@angular/forms';

/**
 * Inline validation message for a single field. Render it directly under (or
 * above) the input it describes and wire the input's `aria-describedby` to this
 * element's `id`.
 *
 * Shows when the bound control is invalid AND has been touched (blur), OR when
 * `forceShow` is set (submit attempt), OR when a `serverError` string is passed.
 * Never shows while the user is still typing an untouched field.
 */
@Component({
  selector: 'app-field-error',
  standalone: true,
  template: `
    @if (isVisible) {
      <p class="field-error" [attr.id]="id()" role="alert">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <span>{{ message }}</span>
      </p>
    }
  `,
})
export class FieldErrorComponent {
  /** The template-driven control, e.g. `#emailCtrl="ngModel"` then `[control]="emailCtrl"`
   *  (don't name the ref after a component property — it shadows it). */
  control = input<NgModel | null>(null);
  /** A message from the server for this field; overrides local validation text. */
  serverError = input<string | null | undefined>(null);
  /** Human label used to build default messages, e.g. "Email". */
  label = input<string>('This field');
  /** Element id, so the input can point `aria-describedby` here. */
  id = input<string | undefined>(undefined);
  /** Override the default message for a given validator key. */
  messages = input<Record<string, string>>({});
  /** Force the message to show even before the field is touched (submit attempt). */
  forceShow = input<boolean>(false);

  get isVisible(): boolean {
    if (this.serverError()) return true;
    const c = this.control();
    if (!c) return false;
    return !!c.invalid && (!!c.touched || this.forceShow());
  }

  get message(): string | null {
    const server = this.serverError();
    if (server) return server;

    const c = this.control();
    const errors = c?.errors;
    if (!errors) return null;

    const custom = this.messages();
    const label = this.label();

    for (const key of Object.keys(errors)) {
      if (custom[key]) return custom[key];
      const info = errors[key];
      switch (key) {
        case 'required':
          return `${label} is required.`;
        case 'email':
          return 'Please enter a valid email address.';
        case 'min':
          return `${label} must be ${info?.min ?? ''} or higher.`.replace('  ', ' ');
        case 'max':
          return `${label} must be ${info?.max ?? ''} or lower.`.replace('  ', ' ');
        case 'minlength':
          return `${label} must be at least ${info?.requiredLength ?? ''} characters.`.replace('  ', ' ');
        case 'maxlength':
          return `${label} must be ${info?.requiredLength ?? ''} characters or fewer.`.replace('  ', ' ');
        case 'pattern':
          return `${label} isn't in the expected format.`;
        default:
          return `Please check ${label.toLowerCase()}.`;
      }
    }
    return null;
  }
}
