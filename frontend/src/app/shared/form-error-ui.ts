import { ErrorListComponent } from './error-list';
import { FieldErrorComponent } from './field-error';
import { FormBannerComponent } from './form-banner';
import { FormSummaryComponent } from './form-summary';
import { InvalidFieldDirective } from './invalid-field';

export { ErrorListComponent } from './error-list';
export { FieldErrorComponent } from './field-error';
export { FormBannerComponent } from './form-banner';
export { FormSummaryComponent } from './form-summary';
export { InvalidFieldDirective } from './invalid-field';
export { parseHttpError } from './http-error';
export type { ParsedHttpError } from './http-error';

/** Spread into a standalone component's `imports` to get the full inline
 *  form-error toolkit: summary box, banner, per-field message, invalid styling. */
export const FORM_ERROR_UI = [
  FormSummaryComponent,
  FormBannerComponent,
  FieldErrorComponent,
  InvalidFieldDirective,
  ErrorListComponent,
] as const;
