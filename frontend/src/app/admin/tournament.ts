import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { LeagueService, Player } from '../league/league';
import { AuthService } from '../auth/auth';

export type MatchFormat = 'doubles' | 'singles' | 'mixed-doubles';

/** Age division. `NN+` presets mean "NN and older"; `custom` carries an explicit range. */
export type AgeGroupKey = 'open' | '19+' | '35+' | '50+' | '60+' | '70+' | 'custom';

/** Options for the age-group dropdown, in the order clubs expect to see them. */
export const AGE_GROUP_OPTIONS: { value: AgeGroupKey; label: string }[] = [
  { value: 'open', label: 'Open (all ages)' },
  { value: '19+', label: '19+' },
  { value: '35+', label: '35+' },
  { value: '50+', label: '50+' },
  { value: '60+', label: '60+' },
  { value: '70+', label: '70+' },
  { value: 'custom', label: 'Custom…' },
];

/** A tournament's age division, or null for Open (so metadata strips stay clean). */
export interface AgeDivision {
  age_group?: string | null;
  age_min?: number | null;
  age_max?: number | null;
}

/**
 * True for any format played in pairs. Mirrors `is_doubles_format` in
 * app/vo/pb/tournament.py — unknown/missing falls back to doubles, the default.
 */
export function isDoublesFormat(fmt?: string | null): boolean {
  return (fmt || 'doubles') !== 'singles';
}

export function formatMatchFormat(fmt?: string | null): string {
  switch (fmt || 'doubles') {
    case 'singles':
      return 'Singles';
    case 'mixed-doubles':
      return 'Mixed Doubles';
    default:
      return 'Doubles';
  }
}

/** Display label for an age division, or null when it is open to all ages. */
export function formatAgeGroup(t?: AgeDivision | null): string | null {
  const group = t?.age_group;
  if (!group || group === 'open') return null;
  if (group !== 'custom') return group;
  const min = t?.age_min ?? null;
  const max = t?.age_max ?? null;
  if (min != null && max != null) return `${min}–${max}`;
  if (min != null) return `${min}+`;
  if (max != null) return `Up to ${max}`;
  return null;
}

export interface TournamentSummary extends AgeDivision {
  tournament_id: string;
  tournament_name: string;
  tournament_status: string;
  tournament_start_date?: string;
  tournament_end_date?: string;
  club_name?: string;
  location?: string;
  match_format?: MatchFormat;
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
  match_format: MatchFormat;
  dupr_min?: number | null;
  dupr_max?: number | null;
  age_group: AgeGroupKey;
  age_min?: number | null;
  age_max?: number | null;
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
    age_group: t.age_group ?? undefined,
    age_min: t.age_min ?? null,
    age_max: t.age_max ?? null,
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

  /** Register the current player; emits the server's response message, errors propagate. */
  registerForTournament(
    tournamentId: string,
    opts: TournamentRegistrationOptions = {}
  ): Observable<string> {
    const user = this.authService.currentUser();
    return this.http
      .post<{ message?: string }>('/api/v1/tournament/register', {
        tournament_id: tournamentId,
        email: user?.email,
        partner_email: opts.partnerEmail || undefined,
        partner_invite_name: opts.inviteName || undefined,
        partner_invite_email: opts.inviteEmail || undefined,
        needs_partner: opts.needsPartner || false,
      })
      .pipe(
        map((res) => {
          this.fetchPlayerTournaments();
          return res?.message ?? 'Player registered successfully';
        })
      );
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
      age_group: input.age_group,
      age_min: input.age_min ?? undefined,
      age_max: input.age_max ?? undefined,
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
