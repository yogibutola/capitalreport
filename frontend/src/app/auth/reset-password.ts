import { Component, inject, NgZone, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from './auth';
import { FORM_ERROR_UI, ParsedHttpError } from '../shared/form-error-ui';

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [FormsModule, RouterLink, ...FORM_ERROR_UI],
  templateUrl: './reset-password.html',
  styleUrl: './login.css'
})
export class ResetPasswordComponent {
  private authService = inject(AuthService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private zone = inject(NgZone);

  token = this.route.snapshot.queryParamMap.get('token') ?? '';

  password = '';
  confirmPassword = '';
  isSubmitting = signal(false);
  submitAttempted = signal(false);
  submitted = signal(false);
  formError = signal<string | null>(null);
  fieldErrors = signal<Record<string, string>>({});

  // Password requirements (shown as a positive checklist, not error messages)
  passwordFocus = false;

  get hasMinLength() { return this.password.length >= 8; }
  get hasUpperCase() { return /[A-Z]/.test(this.password); }
  get hasNumber() { return /[0-9]/.test(this.password); }
  get hasSpecialChar() { return /[@#$]/.test(this.password); }

  get isPasswordValid() {
    return this.hasMinLength && this.hasUpperCase && this.hasNumber && this.hasSpecialChar;
  }

  get passwordsMatch() {
    return this.password === this.confirmPassword;
  }

  clearServerErrors() {
    this.formError.set(null);
    this.fieldErrors.set({});
  }

  onSubmit(form: NgForm) {
    this.submitAttempted.set(true);
    this.clearServerErrors();
    if (this.isSubmitting() || form.invalid || !this.isPasswordValid || !this.passwordsMatch) return;

    this.isSubmitting.set(true);
    this.authService.resetPassword(this.token, this.password).pipe(
      finalize(() => this.zone.run(() => this.isSubmitting.set(false)))
    ).subscribe({
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

  goToLogin() {
    this.router.navigate(['/login']);
  }
}
