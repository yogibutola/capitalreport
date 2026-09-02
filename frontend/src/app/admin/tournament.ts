import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { LeagueService, Player } from '../league/league';
import { AuthService } from '../auth/auth';

export interface TournamentSummary {
  tournament_id: string;
  tournament_name: string;
  tournament_status: string;
  tournament_start_date?: string;
  tournament_end_date?: string;
  club_name?: string;
  location?: string;
  match_format?: 'doubles' | 'singles';
  dupr_min?: number | null;
  dupr_max?: number | null;
  player_count: number;
}

export interface CreateTournamentInput {
  tournament_name: string;
  tournament_description?: string;
  location?: string;
  start_date: Date;
  end_date?: Date;
  match_format: 'doubles' | 'singles';
  dupr_min?: number | null;
  dupr_max?: number | null;
  pool_size: number;
  advancers_per_pool: number;
  player_ids: string[];
}

/** Partner choice a player makes when registering for a doubles tournament. */
export interface TournamentRegistrationOptions {
  partnerEmail?: string;
  inviteName?: string;
  inviteEmail?: string;
  needsPartner?: boolean;
}

function toBackendDate(date: Date): string {
  const mm = String(date.getMonth() + 1).padStart(2, '0');
  const dd = String(date.getDate()).padStart(2, '0');
  return `${mm}-${dd}-${date.getFullYear()}`;
}

function toSummary(t: any): TournamentSummary {
  return {
    tournament_id: String(t.tournament_id),
    tournament_name: t.tournament_name,
    tournament_status: t.tournament_status || 'pending',
    tournament_start_date: t.tournament_start_date,
    tournament_end_date: t.tournament_end_date,
    club_name: t.club_name,
    location: t.location,
    match_format: t.match_format ?? undefined,
    dupr_min: t.dupr_min ?? null,
    dupr_max: t.dupr_max ?? null,
    player_count: Number(t.player_count ?? 0),
  };
}

@Injectable({ providedIn: 'root' })
export class TournamentService {
  private http = inject(HttpClient);
  private leagueService = inject(LeagueService);
  private authService = inject(AuthService);

  tournaments = signal<TournamentSummary[]>([]);

  // Player-facing state: tournaments the current player is registered for, plus
  // every tournament across all clubs for the "Available" discovery tab.
  playerTournaments = signal<TournamentSummary[]>([]);
  private allTournaments = signal<TournamentSummary[]>([]);

  /** Tournaments the player has not joined yet, newest start date first. */
  availableTournaments = computed(() => {
    const registered = new Set(this.playerTournaments().map((t) => t.tournament_id));
    return this.allTournaments()
      .filter((t) => !registered.has(t.tournament_id))
      .sort((a, b) =>
        (b.tournament_start_date ?? '').localeCompare(a.tournament_start_date ?? '')
      );
  });

  fetchTournaments() {
    this.http.get<any[]>('/api/v1/my_tournaments').subscribe({
      next: (data) => this.tournaments.set(data.map(toSummary)),
      error: (err) => console.error('Error fetching tournaments:', err),
    });
  }

  fetchAllTournaments() {
    this.http.get<any[]>('/api/v1/all_tournaments').subscribe({
      next: (data) => this.allTournaments.set((data ?? []).map(toSummary)),
      error: (err) => console.error('Error fetching all tournaments:', err),
    });
  }

  fetchPlayerTournaments() {
    const user = this.authService.currentUser();
    if (!user) {
      this.playerTournaments.set([]);
      return;
    }
    this.http
      .get<any[]>(`/api/v1/player/tournaments/${user.email.toLowerCase()}`)
      .subscribe({
        next: (data) => this.playerTournaments.set((data ?? []).map(toSummary)),
        error: (err) => console.error('Error fetching player tournaments:', err),
      });
  }

  registerForTournament(
    tournamentId: string,
    opts: TournamentRegistrationOptions = {}
  ): Observable<boolean> {
    const user = this.authService.currentUser();
    if (!user) return of(false);
    return this.http
      .post('/api/v1/tournament/register', {
        tournament_id: tournamentId,
        email: user.email,
        partner_email: opts.partnerEmail || undefined,
        partner_invite_name: opts.inviteName || undefined,
        partner_invite_email: opts.inviteEmail || undefined,
        needs_partner: opts.needsPartner || false,
      })
      .pipe(
        map(() => {
          this.fetchPlayerTournaments();
          return true;
        }),
        catchError((err) => {
          console.error('Tournament registration error:', err);
          return of(false);
        })
      );
  }

  /** Register and surface the backend error message on failure (doubles form). */
  registerForTournamentStrict(
    tournamentId: string,
    opts: TournamentRegistrationOptions = {}
  ): Observable<void> {
    const user = this.authService.currentUser();
    return this.http
      .post<void>('/api/v1/tournament/register', {
        tournament_id: tournamentId,
        email: user?.email,
        partner_email: opts.partnerEmail || undefined,
        partner_invite_name: opts.inviteName || undefined,
        partner_invite_email: opts.inviteEmail || undefined,
        needs_partner: opts.needsPartner || false,
      })
      .pipe(map(() => { this.fetchPlayerTournaments(); }));
  }

  generateDraw(tournamentId: string): Observable<any> {
    return this.http.post(`/api/v1/tournament/${tournamentId}/draw`, {});
  }

  unregisterFromTournament(tournamentId: string): Observable<void> {
    return this.http
      .delete<void>(`/api/v1/tournament/${tournamentId}/player`)
      .pipe(
        map(() => {
          this.playerTournaments.update((ts) =>
            ts.filter((t) => t.tournament_id !== tournamentId)
          );
        })
      );
  }

  createTournament(input: CreateTournamentInput) {
    const allPlayers: Player[] = this.leagueService.getPlayers()();
    const selected = allPlayers.filter((p) => input.player_ids.includes(p.id));

    const payload = {
      tournament_id: 0,
      tournament_name: input.tournament_name,
      tournament_description: input.tournament_description || input.tournament_name,
      location: input.location?.trim() || undefined,
      tournament_start_date: toBackendDate(input.start_date),
      tournament_end_date: input.end_date ? toBackendDate(input.end_date) : undefined,
      match_format: input.match_format,
      dupr_min: input.dupr_min ?? undefined,
      dupr_max: input.dupr_max ?? undefined,
      pool_size: input.pool_size,
      advancers_per_pool: input.advancers_per_pool,
      tournament_status: 'pending',
      players: selected.map((p) => ({
        firstName: p.firstName,
        lastName: p.lastName,
        userName: p.userName,
        email: p.email,
        password: p.password || 'temp_pass_123',
        dupr_rating: p.dupr_rating,
      })),
    };

    return this.http.post('/api/v1/tournament', payload);
  }

  deleteTournament(tournamentId: string) {
    return this.http.delete(`/api/v1/tournament/${tournamentId}`);
  }
}
