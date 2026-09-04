import { Component, inject, NgZone, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from './auth';
import { FORM_ERROR_UI, ParsedHttpError } from '../shared/form-error-ui';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [FormsModule, RouterLink, ...FORM_ERROR_UI],
  templateUrl: './forgot-password.html',
  styleUrl: './login.css'
})
export class ForgotPasswordComponent {
  private authService = inject(AuthService);
  private zone = inject(NgZone);

  email = '';
  isSubmitting = signal(false);
  submitAttempted = signal(false);
  submitted = signal(false);
  formError = signal<string | null>(null);
  fieldErrors = signal<Record<string, string>>({});

  clearServerErrors() {
    this.formError.set(null);
    this.fieldErrors.set({});
  }

  onSubmit(form: NgForm) {
    this.submitAttempted.set(true);
    this.clearServerErrors();
    if (this.isSubmitting() || form.invalid) return;

    this.isSubmitting.set(true);
    this.authService.forgotPassword(this.email).pipe(
      finalize(() => this.zone.run(() => this.isSubmitting.set(false)))
    ).subscribe({
      // The backend always returns a generic success response (to avoid
      // leaking which emails are registered), so error is only reachable
      // for things like network failures, not "email not found".
      next: () => this.zone.run(() => this.submitted.set(true)),
      error: (err: ParsedHttpError) => {
        this.zone.run(() => {
          const fieldErrors = err.fieldErrors ?? {};
          this.fieldErrors.set(fieldErrors);
          this.formError.set(Object.keys(fieldErrors).length ? null : err.message);
        });
      }
    });
  }
}
