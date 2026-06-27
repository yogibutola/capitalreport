import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from './auth';

@Component({
  selector: 'app-signup',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './signup.html',
  styleUrl: './signup.css'
})
export class SignupComponent {
  firstName = '';
  lastName = '';
  email = '';
  password = '';
  dupr_rating: number | null = null;
  isSubmitting = false;

  constructor(private authService: AuthService, private router: Router) { }

  onSignup() {
    if (this.firstName && this.lastName && this.email && this.password && this.dupr_rating !== null && !this.isSubmitting) {
      this.isSubmitting = true;

      // Subscribe to the signup observable to wait for response
      this.authService.signupObservable(this.firstName, this.lastName, this.email, this.password, this.dupr_rating).subscribe({
        next: (success) => {
          if (success) {
            this.router.navigate(['/league']);
          }
          this.isSubmitting = false;
        },
        error: (err) => {
          console.error('Signup failed:', err);
          this.isSubmitting = false;
        }
      });
    }
  }
}
