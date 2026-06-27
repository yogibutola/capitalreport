import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from './auth';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './login.html',
  styleUrl: './login.css'
})
export class LoginComponent {
  email = '';
  password = '';
  isSubmitting = false;

  constructor(private authService: AuthService, private router: Router) { }

  onLogin() {
    if (this.email && this.password && !this.isSubmitting) {
      this.isSubmitting = true;
      this.authService.signinObservable(this.email, this.password).subscribe({
        next: (success) => {
          if (success) {
            this.router.navigate(['/league']);
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
