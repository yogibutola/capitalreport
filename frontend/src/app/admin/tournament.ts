import { Injectable, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { LeagueService, Player } from '../league/league';

export interface TournamentSummary {
  tournament_id: string;
  tournament_name: string;
  tournament_status: string;
  tournament_start_date?: string;
  tournament_end_date?: string;
  club_name?: string;
  location?: string;
  player_count: number;
}

export interface CreateTournamentInput {
  tournament_name: string;
  tournament_description?: string;
  location?: string;
  start_date: Date;
  end_date?: Date;
  match_format: 'doubles' | 'singles';
  pool_size: number;
  advancers_per_pool: number;
  player_ids: string[];
}

function toBackendDate(date: Date): string {
  const mm = String(date.getMonth() + 1).padStart(2, '0');
  const dd = String(date.getDate()).padStart(2, '0');
  return `${mm}-${dd}-${date.getFullYear()}`;
}

@Injectable({ providedIn: 'root' })
export class TournamentService {
  private http = inject(HttpClient);
  private leagueService = inject(LeagueService);

  tournaments = signal<TournamentSummary[]>([]);

  fetchTournaments() {
    this.http.get<any[]>('/api/v1/my_tournaments').subscribe({
      next: (data) => {
        this.tournaments.set(
          data.map((t) => ({
            tournament_id: String(t.tournament_id),
            tournament_name: t.tournament_name,
            tournament_status: t.tournament_status || 'pending',
            tournament_start_date: t.tournament_start_date,
            tournament_end_date: t.tournament_end_date,
            club_name: t.club_name,
            location: t.location,
            player_count: Number(t.player_count ?? 0),
          }))
        );
      },
      error: (err) => console.error('Error fetching tournaments:', err),
    });
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
