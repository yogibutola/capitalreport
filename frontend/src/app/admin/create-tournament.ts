import { Component, inject } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import {
  AGE_GROUP_OPTIONS,
  AgeGroupKey,
  MatchFormat,
  TournamentService,
} from './tournament';
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
  format: MatchFormat = 'doubles';
  duprMin: number | null = null;
  duprMax: number | null = null;
  ageGroup: AgeGroupKey = 'open';
  ageMin: number | null = null;
  ageMax: number | null = null;
  poolSize = 4;
  advancersPerPool = 2;

  readonly ageGroups = AGE_GROUP_OPTIONS;

  get duprRangeInvalid(): boolean {
    return (
      this.duprMin != null &&
      this.duprMax != null &&
      this.duprMax < this.duprMin
    );
  }

  get isCustomAgeGroup(): boolean {
    return this.ageGroup === 'custom';
  }

  /** A custom division needs at least one end of the range. */
  get ageRangeMissing(): boolean {
    return this.isCustomAgeGroup && this.ageMin == null && this.ageMax == null;
  }

  get ageRangeInvalid(): boolean {
    return (
      this.isCustomAgeGroup &&
      this.ageMin != null &&
      this.ageMax != null &&
      this.ageMax < this.ageMin
    );
  }

  /** Drop a stale custom range when the dropdown moves back to a preset. */
  onAgeGroupChange() {
    if (!this.isCustomAgeGroup) {
      this.ageMin = null;
      this.ageMax = null;
    }
    this.clearServerErrors();
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
    if (form.invalid || this.duprRangeInvalid || this.ageRangeMissing || this.ageRangeInvalid) {
      if (this.duprRangeInvalid) {
        this.fieldErrors = { ...this.fieldErrors, dupr_max: 'Max rating must be at least the min rating.' };
      }
      if (this.ageRangeMissing) {
        this.fieldErrors = {
          ...this.fieldErrors,
          age_group: 'Set a minimum or maximum age for a custom age group.',
        };
      }
      if (this.ageRangeInvalid) {
        this.fieldErrors = { ...this.fieldErrors, age_max: 'Max age must be at least the min age.' };
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
        age_group: this.ageGroup,
        // Presets carry no bounds of their own — the backend derives them.
        age_min: this.isCustomAgeGroup ? this.ageMin : null,
        age_max: this.isCustomAgeGroup ? this.ageMax : null,
        pool_size: this.poolSize,
        advancers_per_pool: this.advancersPerPool,
        player_ids: [],
      })
      .subscribe({
        next: () => {
          this.tournamentService.fetchTournaments();
          this.router.navigate(['/admin/tournaments']);
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
