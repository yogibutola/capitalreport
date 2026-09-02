import { Component, inject } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { TournamentService } from './tournament';
import { FORM_ERROR_UI, parseHttpError } from '../shared/form-error-ui';

@Component({
  selector: 'app-create-tournament',
  standalone: true,
  imports: [FormsModule, RouterLink, ...FORM_ERROR_UI],
  templateUrl: './create-tournament.html',
  styleUrl: './create-league.css',
})
export class CreateTournamentComponent {
  private tournamentService = inject(TournamentService);
  private router = inject(Router);

  // Form model
  name = '';
  description = '';
  location = '';
  startDate = '';
  endDate = '';
  format: 'doubles' | 'singles' = 'doubles';
  duprMin: number | null = null;
  duprMax: number | null = null;
  poolSize = 4;
  advancersPerPool = 2;

  get duprRangeInvalid(): boolean {
    return (
      this.duprMin != null &&
      this.duprMax != null &&
      this.duprMax < this.duprMin
    );
  }

  submitting = false;
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
    if (this.submitting) return;
    if (form.invalid || this.duprRangeInvalid) {
      if (this.duprRangeInvalid) {
        this.fieldErrors = { dupr_max: 'Max rating must be at least the min rating.' };
      }
      return;
    }

    this.submitting = true;
    this.tournamentService
      .createTournament({
        tournament_name: this.name.trim(),
        tournament_description: this.description.trim() || undefined,
        location: this.location,
        start_date: new Date(this.startDate),
        end_date: this.endDate ? new Date(this.endDate) : undefined,
        match_format: this.format,
        dupr_min: this.duprMin,
        dupr_max: this.duprMax,
        pool_size: this.poolSize,
        advancers_per_pool: this.advancersPerPool,
        player_ids: [],
      })
      .subscribe({
        next: () => {
          this.tournamentService.fetchTournaments();
          this.router.navigate(['/admin']);
        },
        error: (err) => {
          this.submitting = false;
          const parsed = parseHttpError(err);
          this.fieldErrors = { ...parsed.fieldErrors };
          this.formError = parsed.message;
        },
      });
  }
}
