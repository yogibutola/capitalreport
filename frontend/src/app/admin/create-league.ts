import { Component, inject } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AdminService } from './admin';
import { FORM_ERROR_UI, ParsedHttpError } from '../shared/form-error-ui';

@Component({
  selector: 'app-create-league',
  standalone: true,
  imports: [FormsModule, RouterLink, ...FORM_ERROR_UI],
  templateUrl: './create-league.html',
  styleUrl: './create-league.css'
})
export class CreateLeagueComponent {
  adminService = inject(AdminService);
  router = inject(Router);

  // Form Model
  name = '';
  location = '';
  startDate = '';
  durationWeeks = 10;
  groupSize = 5;
  format: 'round-robin' | 'other' = 'round-robin';

  isSubmitting = false;
  submitAttempted = false;
  formError: string | null = null;
  fieldErrors: Record<string, string> = {};

  clearServerErrors() {
    this.formError = null;
    this.fieldErrors = {};
  }

  onSubmit(form: NgForm) {
    this.submitAttempted = true;
    this.clearServerErrors();
    if (this.isSubmitting) return;
    if (form.invalid) {
      return;
    }

    this.isSubmitting = true;
    this.adminService
      .createLeague({
        league_name: this.name.trim(),
        league_description: this.name.trim(),
        location: this.location.trim() || undefined,
        league_start_date: new Date(this.startDate),
        league_duration: this.durationWeeks,
        group_size: this.groupSize,
        match_format: this.format,
        player_ids: []
      })
      .subscribe({
        next: () => {
          this.isSubmitting = false;
          this.router.navigate(['/admin']);
        },
        error: (err: ParsedHttpError) => {
          this.isSubmitting = false;
          this.fieldErrors = { ...err.fieldErrors };
          this.formError = err.message;
        }
      });
  }
}
