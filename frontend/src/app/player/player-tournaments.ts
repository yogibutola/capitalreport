import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { TournamentService, TournamentSummary } from '../admin/tournament';
import { LeagueService } from '../league/league';
import { AuthService } from '../auth/auth';
import { ToastService } from '../shared/toast.service';
import { ConfirmService } from '../shared/confirm.service';
import { parseHttpError } from '../shared/http-error';

@Component({
  selector: 'app-player-tournaments',
  standalone: true,
  imports: [RouterLink, FormsModule],
  templateUrl: './player-tournaments.html',
  styleUrl: './player-tournaments.css',
})
export class PlayerTournamentsComponent implements OnInit {
  private tournamentService = inject(TournamentService);
  private leagueService = inject(LeagueService);
  private auth = inject(AuthService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private toast = inject(ToastService);
  private confirm = inject(ConfirmService);

  myTournaments = this.tournamentService.playerTournaments;
  availableTournaments = this.tournamentService.availableTournaments;

  activeTab = signal<'my' | 'available'>('my');

  // Doubles registration panel: which tournament's form is open + its state.
  registeringId = signal<string | null>(null);
  partnerMode = signal<'have' | 'looking'>('looking');
  inviteMode = signal(false);
  partnerId = '';
  inviteName = '';
  inviteEmail = '';
  submitting = signal(false);

  /** Player accounts other than the current user, for the partner dropdown. */
  partnerOptions = computed(() => {
    const me = this.auth.currentUser()?.email?.toLowerCase();
    return this.leagueService.getPlayers()().filter((p) => p.email.toLowerCase() !== me);
  });

  ngOnInit() {
    this.tournamentService.fetchPlayerTournaments();
    this.tournamentService.fetchAllTournaments();
    this.leagueService.fetchPlayers();
    if (this.route.snapshot.queryParamMap.get('tab') === 'available') {
      this.activeTab.set('available');
    }
  }

  viewTournament(tournamentId: string) {
    this.router.navigate(['/player/tournament', tournamentId]);
  }

  duprRange(t: TournamentSummary): string | null {
    if (t.dupr_min == null && t.dupr_max == null) return null;
    return `DUPR ${t.dupr_min ?? '0'}–${t.dupr_max ?? '8'}`;
  }

  /** Entry point from the "Register" button — branches on format. */
  async startRegister(t: TournamentSummary) {
    if (t.match_format === 'doubles') {
      this.resetPanel();
      this.registeringId.set(t.tournament_id);
      return;
    }
    const confirmed = await this.confirm.ask({
      title: 'Register for this tournament?',
      message:
        'You will be added to the player roster and seeded into the pools when the draw is generated.',
      confirmLabel: 'Register',
      cancelLabel: 'Not Now',
      tone: 'primary',
    });
    if (!confirmed) return;

    this.tournamentService.registerForTournament(t.tournament_id).subscribe((success) => {
      if (success) {
        this.toast.success("You're registered for this tournament.");
      } else {
        this.toast.error(
          "We couldn't complete your registration. Registration may be closed for this tournament."
        );
      }
    });
  }

  cancelPanel() {
    this.registeringId.set(null);
  }

  private resetPanel() {
    this.partnerMode.set('looking');
    this.inviteMode.set(false);
    this.partnerId = '';
    this.inviteName = '';
    this.inviteEmail = '';
  }

  submitDoubles(tournamentId: string) {
    if (this.submitting()) return;

    let opts;
    if (this.partnerMode() === 'looking') {
      opts = { needsPartner: true };
    } else if (this.inviteMode()) {
      if (!this.inviteName.trim() || !this.inviteEmail.trim()) {
        this.toast.error("Enter your partner's name and email, or switch to 'looking for a partner'.");
        return;
      }
      opts = { inviteName: this.inviteName.trim(), inviteEmail: this.inviteEmail.trim() };
    } else {
      if (!this.partnerId) {
        this.toast.error('Pick a partner from the list, or invite one by email.');
        return;
      }
      opts = { partnerEmail: this.partnerId };
    }

    this.submitting.set(true);
    this.tournamentService.registerForTournamentStrict(tournamentId, opts).subscribe({
      next: () => {
        this.submitting.set(false);
        this.registeringId.set(null);
        this.tournamentService.fetchAllTournaments();
        this.toast.success("You're registered for this tournament.");
      },
      error: (err) => {
        this.submitting.set(false);
        this.toast.error(parseHttpError(err).message);
      },
    });
  }

  async withdraw(tournamentId: string, tournamentName: string) {
    const confirmed = await this.confirm.ask({
      title: `Withdraw from ${tournamentName}?`,
      message:
        'You will be removed from the roster and the pools will be redrawn without you. This cannot be undone.',
      confirmLabel: 'Withdraw',
      cancelLabel: 'Stay Registered',
    });
    if (!confirmed) return;

    this.tournamentService.unregisterFromTournament(tournamentId).subscribe({
      next: () => {
        this.tournamentService.fetchAllTournaments();
        this.toast.success(`You've withdrawn from "${tournamentName}".`);
      },
      error: (err) => this.toast.error(parseHttpError(err).message),
    });
  }

  /** Backend dates are mm-dd-yyyy strings; fall back to the raw value. */
  formatDate(date?: string): string {
    if (!date) return '—';
    const [mm, dd, yyyy] = date.split('-').map(Number);
    if (!mm || !dd || !yyyy) return date;
    return new Date(yyyy, mm - 1, dd).toLocaleDateString();
  }
}
