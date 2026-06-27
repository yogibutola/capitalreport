import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../auth/auth';

@Component({
    selector: 'app-admin-login',
    standalone: true,
    imports: [FormsModule, RouterLink],
    templateUrl: './admin-login.html',
    styleUrl: '../auth/login.css' // Reuse login styles
})
export class AdminLoginComponent {
    email = '';
    password = '';
    isSubmitting = false;

    constructor(private authService: AuthService, private router: Router) { }

    onLogin() {
        if (this.email && this.password && !this.isSubmitting) {
            this.isSubmitting = true;
            // For now, we use the same auth service. In a real app, you might have role checks here.
            this.authService.signinObservable(this.email, this.password).subscribe({
                next: (success) => {
                    if (success) {
                        // Redirect to Admin Dashboard instead of Player
                        this.router.navigate(['/admin']);
                    }
                    this.isSubmitting = false;
                },
                error: (err) => {
                    console.error('Signin failed:', err);
                    this.isSubmitting = false;
                }
            });
        }
    }
}
