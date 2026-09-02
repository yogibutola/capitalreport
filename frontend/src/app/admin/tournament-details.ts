import { Component, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { TournamentService } from './tournament';
import { ConfirmService } from '../shared/confirm.service';
import { ToastService } from '../shared/toast.service';
import { parseHttpError } from '../shared/http-error';

interface PoolMatch {
  match_id: string;
  participant_one_email?: string | null;
  participant_two_email?: string | null;
  participant_one_name?: string;
  participant_two_name?: string;
  score_one: number;
  score_two: number;
  match_status: string;
}

interface TournamentTeam {
  team_id: string;
  team_name: string;
  player_one_name: string;
  player_two_name?: string | null;
  dupr_rating?: number;
  formed_by?: string;
}

interface Pool {
  pool_id: number;
  pool_name: string;
  players: { firstName: string; lastName: string; dupr_rating?: number }[];
  teams: TournamentTeam[];
  matches: PoolMatch[];
}

interface KnockoutMatch {
  match_id: string;
  slot_one_label: string;
  slot_two_label: string;
  participant_one_email?: string | null;
  participant_two_email?: string | null;
  participant_one_name?: string;
  participant_two_name?: string;
  score_one: number;
  score_two: number;
  match_status: string;
}

type Scorable = {
  match_id: string;
  participant_one_email?: string | null;
  participant_two_email?: string | null;
  match_status: string;
};

interface KnockoutRound {
  round_id: number;
  round_name: string;
  matches: KnockoutMatch[];
}

interface TournamentRegistration {
  firstName: string;
  lastName: string;
  email: string;
  dupr_rating?: number | null;
  needs_partner?: boolean;
  partner_email?: string | null;
  partner_name?: string | null;
  partner_registered?: boolean;
}

interface TournamentDetail {
  tournament_id: string;
  tournament_name: string;
  tournament_status?: string;
  tournament_start_date?: string;
  tournament_end_date?: string;
  match_format?: string;
  dupr_min?: number | null;
  dupr_max?: number | null;
  club_name?: string;
  location?: string;
  registrations: TournamentRegistration[];
  teams: TournamentTeam[];
  pools: Pool[];
  knockout: KnockoutRound[];
}

@Component({
  selector: 'app-tournament-details',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './tournament-details.html',
})
export class TournamentDetailsComponent {
  private http = inject(HttpClient);
  private route = inject(ActivatedRoute);
  private tournamentService = inject(TournamentService);
  private confirm = inject(ConfirmService);
  private toast = inject(ToastService);

  tournament = signal<TournamentDetail | null>(null);
  loading = signal(true);
  error = signal('');
  drawing = signal(false);
  savingMatch = signal<string | null>(null);

  // Players reach this page from /player/tournament/:id; admins from /admin/tournament/:id.
  isAdminView = this.route.snapshot.url.some((s) => s.path === 'admin');
  backLink = this.isAdminView ? '/admin' : '/player/tournaments';

  isDoubles = computed(() => this.tournament()?.match_format === 'doubles');
  isPending = computed(() => (this.tournament()?.tournament_status ?? 'pending') === 'pending');

  /** Matches whose participants are known but whose score hasn't been entered. */
  pendingResultCount = computed(() => {
    const t = this.tournament();
    if (!t) return 0;
    const poolMatches = (t.pools ?? []).flatMap((p) => p.matches ?? []);
    const koMatches = (t.knockout ?? []).flatMap((r) => r.matches ?? []);
    return [...poolMatches, ...koMatches].filter(
      (m) =>
        !this.isDone(m) && !!m.participant_one_email && !!m.participant_two_email
    ).length;
  });

  /** Registrations still without a partner (auto-paired at draw time). */
  soloRegistrations = computed(() =>
    (this.tournament()?.registrations ?? []).filter((r) => !r.partner_email)
  );
  /** Email invites for partners who don't have an account yet. */
  unresolvedInvites = computed(() =>
    (this.tournament()?.registrations ?? []).filter(
      (r) => r.partner_email && !r.partner_registered
    )
  );
  formedTeams = computed(() =>
    (this.tournament()?.registrations ?? []).filter((r) => r.partner_email)
  );
  soloNames = computed(() =>
    this.soloRegistrations()
      .map((r) => `${r.firstName} ${r.lastName}`.trim())
      .join(', ')
  );

  constructor() {
    this.load();
  }

  private load() {
    const id = this.route.snapshot.paramMap.get('tournament_id');
    if (!id) {
      this.error.set('Missing tournament id');
      this.loading.set(false);
      return;
    }
    this.loading.set(true);
    this.http.get<TournamentDetail>(`/api/v1/tournament/id/${id}`).subscribe({
      next: (data) => {
        this.tournament.set(data);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail || 'Failed to load tournament');
        this.loading.set(false);
      },
    });
  }

  async generateDraw() {
    const t = this.tournament();
    if (!t || this.drawing()) return;
    const confirmed = await this.confirm.ask({
      title: 'Close registration & generate the draw?',
      message:
        'The roster will be locked, players looking for a partner will be paired by rating, and the pools and knockout bracket will be built.',
      confirmLabel: 'Generate Draw',
      cancelLabel: 'Not Yet',
      tone: 'primary',
    });
    if (!confirmed) return;

    this.drawing.set(true);
    this.tournamentService.generateDraw(t.tournament_id).subscribe({
      next: (summary) => {
        this.drawing.set(false);
        const auto = summary?.auto_paired ? ` · ${summary.auto_paired} pair(s) auto-formed` : '';
        this.toast.success(`Draw generated${auto}.`);
        this.load();
      },
      error: (err) => {
        this.drawing.set(false);
        this.toast.error(parseHttpError(err).message);
      },
    });
  }

  playerName(p: { firstName: string; lastName: string }) {
    return `${p.firstName} ${p.lastName}`.trim();
  }

  /** Admin can enter a score once both participants of a match are decided. */
  canScore(m: Scorable) {
    return (
      this.isAdminView &&
      !this.isPending() &&
      !!m.participant_one_email &&
      !!m.participant_two_email
    );
  }

  isDone(m: { match_status?: string }) {
    return m.match_status === 'Completed' || m.match_status === 'Bye';
  }

  saveScore(m: Scorable, stage: 'pool' | 'knockout', a: string, b: string) {
    const t = this.tournament();
    if (!t || this.savingMatch()) return;

    const s1 = Number(a);
    const s2 = Number(b);
    if (!Number.isInteger(s1) || !Number.isInteger(s2) || s1 < 0 || s2 < 0) {
      this.toast.error('Enter two non-negative whole-number scores.');
      return;
    }
    if (stage === 'knockout' && s1 === s2) {
      this.toast.error('A knockout match needs a winner — scores can’t be tied.');
      return;
    }

    this.savingMatch.set(m.match_id);
    this.http
      .post<TournamentDetail>(`/api/v1/tournament/${t.tournament_id}/match/score`, {
        match_id: m.match_id,
        stage,
        score_one: s1,
        score_two: s2,
      })
      .subscribe({
        next: (data) => {
          this.tournament.set(data);
          this.savingMatch.set(null);
          this.toast.success('Score saved.');
        },
        error: (err) => {
          this.savingMatch.set(null);
          this.toast.error(parseHttpError(err).message);
        },
      });
  }
}
