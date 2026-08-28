import { Component, inject, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from './auth';
import { FORM_ERROR_UI, ParsedHttpError } from '../shared/form-error-ui';

@Component({
  selector: 'app-signup',
  standalone: true,
  imports: [FormsModule, RouterLink, ...FORM_ERROR_UI],
  templateUrl: './signup.html',
  styleUrl: './signup.css'
})
export class SignupComponent {
  private authService = inject(AuthService);
  private router = inject(Router);

  firstName = '';
  lastName = '';
  email = '';
  password = '';
  dupr_rating: number | null = null;
  isSubmitting = signal(false);
  submitAttempted = signal(false);
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

  clearServerErrors() {
    this.formError.set(null);
    this.fieldErrors.set({});
  }

  onSignup(form: NgForm) {
    this.submitAttempted.set(true);
    this.clearServerErrors();
    if (this.isSubmitting() || form.invalid || !this.isPasswordValid) return;

    this.isSubmitting.set(true);
    this.authService
      .signupObservable(this.firstName, this.lastName, this.email, this.password, this.dupr_rating!)
      .subscribe({
        next: (success) => {
          this.isSubmitting.set(false);
          if (success) this.router.navigate(['/league']);
        },
        error: (err: ParsedHttpError) => {
          this.isSubmitting.set(false);
          const fieldErrors = { ...err.fieldErrors };
          this.fieldErrors.set(fieldErrors);
          // Backend calls it dupr_rating; keep the same key our template uses.
          this.formError.set(Object.keys(fieldErrors).length
            ? 'Please correct the highlighted fields and try again.'
            : err.message);
        }
      });
  }
}
