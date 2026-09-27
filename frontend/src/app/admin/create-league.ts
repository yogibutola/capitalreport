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
  duprMin: number | null = null;
  duprMax: number | null = null;

  isSubmitting = false;
  submitAttempted = false;
  formError: string | null = null;
  fieldErrors: Record<string, string> = {};

  /** Both bounds are optional, but an inverted range is never valid. */
  get duprRangeInvalid(): boolean {
    return this.duprMin != null && this.duprMax != null && this.duprMax < this.duprMin;
  }

  clearServerErrors() {
    this.formError = null;
    this.fieldErrors = {};
  }

  onSubmit(form: NgForm) {
    this.submitAttempted = true;
    this.clearServerErrors();
    if (this.isSubmitting) return;
    if (form.invalid || this.duprRangeInvalid) {
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
        dupr_min: this.duprMin,
        dupr_max: this.duprMax,
        player_ids: []
      })
      .subscribe({
        next: () => {
          this.isSubmitting = false;
          this.router.navigate(['/admin/leagues']);
        },
        error: (err: ParsedHttpError) => {
          this.isSubmitting = false;
          this.fieldErrors = { ...err.fieldErrors };
          this.formError = err.message;
        }
      });
  }
}
