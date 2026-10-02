import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Observable } from 'rxjs';
import { AuthService } from '../auth/auth';
import { FORM_ERROR_UI, ParsedHttpError } from '../shared/form-error-ui';
import { BrandLogoComponent } from '../shared/brand-logo';
import { BrandMarkComponent } from '../shared/brand-mark';

/**
 * "Register your club".
 *
 * A club is run by a person, so there are two ways in:
 *  - a visitor signs up as the organiser (their own account) and creates the club in one step;
 *  - a signed-in player just names their club - they already have an account.
 * Either way the session ends up with the admin role for the new club.
 */
@Component({
    selector: 'app-club-signup',
    standalone: true,
    imports: [FormsModule, RouterLink, ...FORM_ERROR_UI, BrandLogoComponent, BrandMarkComponent],
    templateUrl: './club-signup.html',
    styleUrl: '../auth/signup.css' // Reuse signup styles
})
export class ClubSignupComponent {
    private authService = inject(AuthService);
    private router = inject(Router);

    /** Signed in as a player: only the club details are needed. */
    signedInPlayer = computed(() => {
        const user = this.authService.currentUser();
        return !!user && user.role === 'player';
    });
    /** Signed in and already running a club. */
    alreadyRunsAClub = computed(() => this.authService.currentUser()?.role === 'admin');

    firstName = '';
    lastName = '';
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
        const needsPassword = !this.signedInPlayer();
        if (this.isSubmitting() || form.invalid || (needsPassword && !this.isPasswordValid)) return;

        this.isSubmitting.set(true);
        const address = this.address.trim() || null;
        const phone = this.phone.trim() || null;
        const request: Observable<unknown> = this.signedInPlayer()
            ? this.authService.createClub({ name: this.clubName.trim(), address, phone })
            : this.authService.signupClubObservable({
                firstName: this.firstName.trim(),
                lastName: this.lastName.trim(),
                clubName: this.clubName.trim(),
                email: this.email.trim(),
                password: this.password,
                address,
                phone,
            });

        request.subscribe({
            next: () => {
                this.isSubmitting.set(false);
                this.router.navigate(['/admin']);
            },
            error: (err: ParsedHttpError) => {
                this.isSubmitting.set(false);
                // POST /clubs names the club field "name"; the form calls it clubName.
                const fieldErrors: Record<string, string> = { ...err.fieldErrors };
                if (fieldErrors['name']) {
                    fieldErrors['clubName'] = fieldErrors['name'];
                    delete fieldErrors['name'];
                }
                this.fieldErrors.set(fieldErrors);
                this.formError.set(Object.keys(fieldErrors).length
                    ? 'Please correct the highlighted fields and try again.'
                    : err.message);
            }
        });
    }
}
