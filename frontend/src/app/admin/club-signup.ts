import { Component, inject, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../auth/auth';
import { FORM_ERROR_UI, ParsedHttpError } from '../shared/form-error-ui';

@Component({
    selector: 'app-club-signup',
    standalone: true,
    imports: [FormsModule, RouterLink, ...FORM_ERROR_UI],
    templateUrl: './club-signup.html',
    styleUrl: '../auth/signup.css' // Reuse signup styles
})
export class ClubSignupComponent {
    private authService = inject(AuthService);
    private router = inject(Router);

    clubName = '';
    email = '';
    password = '';
    address = '';
    phone = '';
    isSubmitting = signal(false);
    submitAttempted = signal(false);
    formError = signal<string | null>(null);
    fieldErrors = signal<Record<string, string>>({});

    // Password requirements (positive checklist, not error messages)
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
            .signupClubObservable(this.clubName, this.email, this.password, this.address, this.phone)
            .subscribe({
                next: (success) => {
                    this.isSubmitting.set(false);
                    if (success) this.router.navigate(['/admin']);
                },
                error: (err: ParsedHttpError) => {
                    this.isSubmitting.set(false);
                    const fieldErrors = { ...err.fieldErrors };
                    this.fieldErrors.set(fieldErrors);
                    this.formError.set(Object.keys(fieldErrors).length
                        ? 'Please correct the highlighted fields and try again.'
                        : err.message);
                }
            });
    }
}
