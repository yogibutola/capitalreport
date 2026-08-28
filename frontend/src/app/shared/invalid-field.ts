import { Directive, input } from '@angular/core';
import { NgModel } from '@angular/forms';

/**
 * Toggles `.is-invalid` and `aria-invalid` on an input from its template-driven
 * control state. Pairs with `<app-field-error>` (same inputs) placed just after
 * the field.
 *
 * Give the template ref a name that does NOT clash with a component property
 * (e.g. `#emailCtrl`, not `#email`) — a clashing ref shadows the property and
 * breaks `[(ngModel)]`.
 *
 *   <input #emailCtrl="ngModel" name="email" [(ngModel)]="email" required email
 *          [appInvalid]="emailCtrl"
 *          [appInvalidServer]="fieldErrors['email']"
 *          [appInvalidForce]="submitAttempted">
 */
@Directive({
  selector: '[appInvalid]',
  standalone: true,
  host: {
    '[class.is-invalid]': 'isInvalid',
    '[attr.aria-invalid]': 'isInvalid ? "true" : null',
  },
})
export class InvalidFieldDirective {
  control = input<NgModel | null>(null, { alias: 'appInvalid' });
  serverError = input<string | null | undefined>(null, { alias: 'appInvalidServer' });
  forceShow = input<boolean>(false, { alias: 'appInvalidForce' });

  get isInvalid(): boolean {
    if (this.serverError()) return true;
    const c = this.control();
    return !!c?.invalid && (!!c.touched || this.forceShow());
  }
}
