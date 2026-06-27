import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common'; // Import CommonModule for ngIf, ngClass etc.
import { AuthService } from '../auth/auth';

@Component({
    selector: 'app-club-signup',
    standalone: true,
    imports: [FormsModule, RouterLink, CommonModule],
    templateUrl: './club-signup.html',
    styleUrl: '../auth/signup.css' // Reuse signup styles
})
export class ClubSignupComponent {
    clubName = '';
    email = '';
    password = '';
    address = '';
    phone = '';
    isSubmitting = false;

    // Password Validation State
    passwordFocus = false;

    get hasMinLength() { return this.password.length >= 8; }
    get hasUpperCase() { return /[A-Z]/.test(this.password); }
    get hasNumber() { return /[0-9]/.test(this.password); }
    get hasSpecialChar() { return /[@#$]/.test(this.password); }

    get isPasswordValid() {
        return this.hasMinLength && this.hasUpperCase && this.hasNumber && this.hasSpecialChar;
    }

    constructor(private authService: AuthService, private router: Router) { }

    onSignup() {
        if (this.isFormValid() && !this.isSubmitting) {
            this.isSubmitting = true;
            this.authService.signupClubObservable(
                this.clubName,
                this.email,
                this.password,
                this.address,
                this.phone
            ).subscribe({
                next: (success) => {
                    if (success) {
                        this.router.navigate(['/admin']);
                    }
                    this.isSubmitting = false;
                },
                error: (err) => {
                    console.error('Club signup failed:', err);
                    this.isSubmitting = false;
                }
            });
        }
    }

    isFormValid(): boolean {
        return !!(
            this.clubName &&
            this.email &&
            this.isPasswordValid &&
            this.address &&
            this.phone
        );
    }
}
