import { Component, inject, NgZone, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../auth/auth';
import { FORM_ERROR_UI, ParsedHttpError } from '../shared/form-error-ui';

@Component({
    selector: 'app-platform-login',
    standalone: true,
    imports: [FormsModule, ...FORM_ERROR_UI],
    templateUrl: './platform-login.html',
    styleUrl: '../auth/login.css',
})
export class PlatformLoginComponent {
    private authService = inject(AuthService);
    private router = inject(Router);
    private zone = inject(NgZone);

    email = '';
    password = '';
    isSubmitting = signal(false);
    submitAttempted = signal(false);
    formError = signal<string | null>(null);
    fieldErrors = signal<Record<string, string>>({});

    clearServerErrors() {
        this.formError.set(null);
        this.fieldErrors.set({});
    }

    onLogin(form: NgForm) {
        this.submitAttempted.set(true);
        this.clearServerErrors();
        if (this.isSubmitting() || form.invalid) return;

        this.isSubmitting.set(true);
        this.authService
            .signinObservable(this.email, this.password)
            .pipe(finalize(() => this.zone.run(() => this.isSubmitting.set(false))))
            .subscribe({
                next: (success) => {
                    if (!success) return;
                    if (this.authService.isSuperAdmin()) {
                        this.router.navigate(['/x9k2-console']);
                    } else {
                        this.authService.logout();
                        this.formError.set('This account is not a platform administrator.');
                    }
                },
                error: (err: ParsedHttpError) => {
                    this.zone.run(() => {
                        const fieldErrors = err.fieldErrors ?? {};
                        this.fieldErrors.set(fieldErrors);
                        this.formError.set(Object.keys(fieldErrors).length ? null : err.message);
                    });
                },
            });
    }
}
