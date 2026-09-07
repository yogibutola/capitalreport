import { Component, computed, inject, OnInit, PLATFORM_ID, signal } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { FormsModule, NgForm } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../auth/auth';
import { ToastService } from '../shared/toast.service';
import { FORM_ERROR_UI, ParsedHttpError, parseHttpError } from '../shared/form-error-ui';

interface PublicTournament {
  tournament_id: string;
  tournament_name: string;
  tournament_description?: string;
  tournament_status?: string;
  tournament_start_date?: string;
  tournament_end_date?: string;
  match_format?: 'singles' | 'doubles';
  dupr_min?: number | null;
  dupr_max?: number | null;
  club_name?: string;
  location?: string;
}

/**
 * Public "Register for Tournament" page for people who don't have an account yet.
 *
 * Reached from the share link an organiser embeds on a tournament flyer/image
 * (`/register-tournament/:tournament_id`). Creates the player account and
 * registers it for the tournament in one submit, then drops the user into a
 * logged-in session.
 */
@Component({
  selector: 'app-tournament-register',
  standalone: true,
  imports: [FormsModule, RouterLink, ...FORM_ERROR_UI],
  templateUrl: './tournament-register.html',
  styleUrl: './tournament-register.css',
})
export class TournamentRegisterComponent implements OnInit {
  private http = inject(HttpClient);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private auth = inject(AuthService);
  private toast = inject(ToastService);
  private platformId = inject(PLATFORM_ID);

  tournamentId = '';
  tournament = signal<PublicTournament | null>(null);
  loading = signal(true);
  loadError = signal<string | null>(null);

  // Registration form
  firstName = '';
  lastName = '';
  email = '';
  password = '';
  dupr_rating: number | null = null;
  partnerChoice = signal<'looking' | 'invite'>('looking');
  inviteName = '';
  inviteEmail = '';

  submitting = signal(false);
  submitAttempted = signal(false);
  formError = signal<string | null>(null);
  fieldErrors = signal<Record<string, string>>({});
  passwordFocus = false;

  // Success state
  done = signal(false);
  // The registrant already has an account — point them at sign-in instead.
  accountExists = signal(false);

  isDoubles = computed(() => this.tournament()?.match_format === 'doubles');
  isClosed = computed(
    () => !!this.tournament() && (this.tournament()!.tournament_status ?? 'pending') !== 'pending'
  );

  duprRange = computed(() => {
    const t = this.tournament();
    if (!t || (t.dupr_min == null && t.dupr_max == null)) return null;
    return `${t.dupr_min ?? '0.0'} – ${t.dupr_max ?? '8.0'}`;
  });

  loginLink = computed(() => `/login?redirect=/register-tournament/${this.tournamentId}`);

  get hasMinLength() { return this.password.length >= 8; }
  get hasUpperCase() { return /[A-Z]/.test(this.password); }
  get hasNumber() { return /[0-9]/.test(this.password); }
  get hasSpecialChar() { return /[@#$]/.test(this.password); }
  get isPasswordValid() {
    return this.hasMinLength && this.hasUpperCase && this.hasNumber && this.hasSpecialChar;
  }

  ngOnInit() {
    this.tournamentId = this.route.snapshot.paramMap.get('tournament_id') ?? '';
    if (!this.tournamentId) {
      this.loadError.set('This registration link is missing a tournament.');
      this.loading.set(false);
      return;
    }
    // Already signed in? The public "create an account" form is the wrong tool —
    // send them to the authenticated flow instead.
    if (this.auth.isLoggedIn()) {
      if (this.auth.isAdmin()) {
        this.router.navigate(['/admin/tournament', this.tournamentId]);
      } else {
        this.toast.success('You’re already signed in — register from the Available tab.');
        this.router.navigate(['/player/tournaments'], { queryParams: { tab: 'available' } });
      }
      return;
    }
    this.http.get<PublicTournament>(`/api/v1/tournament/id/${this.tournamentId}`).subscribe({
      next: (data) => {
        this.tournament.set(data);
        this.loading.set(false);
      },
      error: (err) => {
        this.loadError.set(
          err?.status === 404
            ? "We couldn't find that tournament. The link may be out of date."
            : parseHttpError(err).message
        );
        this.loading.set(false);
      },
    });
  }

  clearServerErrors() {
    this.formError.set(null);
    this.fieldErrors.set({});
    this.accountExists.set(false);
  }

  formatDate(date?: string): string {
    if (!date) return '';
    const [mm, dd, yyyy] = date.split('-').map(Number);
    if (!mm || !dd || !yyyy) return date;
    return new Date(yyyy, mm - 1, dd).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  }

  submit(form: NgForm) {
    this.submitAttempted.set(true);
    this.clearServerErrors();
    if (this.submitting() || form.invalid || !this.isPasswordValid) return;

    const invite = this.isDoubles() && this.partnerChoice() === 'invite';
    if (invite && (!this.inviteName.trim() || !this.inviteEmail.trim())) {
      this.formError.set("Enter your partner's name and email, or choose “I'll find a partner”.");
      return;
    }

    const payload = {
      tournament_id: this.tournamentId,
      firstName: this.firstName.trim(),
      lastName: this.lastName.trim(),
      email: this.email.trim(),
      password: this.password,
      dupr_rating: this.dupr_rating,
      needs_partner: this.isDoubles() && !invite,
      partner_invite_name: invite ? this.inviteName.trim() : undefined,
      partner_invite_email: invite ? this.inviteEmail.trim() : undefined,
    };

    this.submitting.set(true);
    this.http.post<any>('/api/v1/tournament/register/public', payload).subscribe({
      next: (res) => {
        this.submitting.set(false);
        this.auth.adoptSession(res);
        this.done.set(true);
      },
      error: (err: ParsedHttpError | unknown) => {
        this.submitting.set(false);
        const parsed = parseHttpError(err);
        if (parsed.status === 409) {
          this.accountExists.set(true);
          this.formError.set(parsed.message);
          return;
        }
        this.fieldErrors.set(parsed.fieldErrors ?? {});
        this.formError.set(
          Object.keys(parsed.fieldErrors ?? {}).length
            ? 'Please correct the highlighted fields and try again.'
            : parsed.message
        );
      },
    });
  }

  goToTournament() {
    this.router.navigate(['/player/tournament', this.tournamentId]);
  }
}
