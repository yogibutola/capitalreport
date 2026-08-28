import { Injectable, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, throwError } from 'rxjs';
import { LeagueService } from '../league/league';
import { ToastService } from '../shared/toast.service';
import { ConfirmService } from '../shared/confirm.service';
import { parseHttpError } from '../shared/http-error';

export interface League {
  league_id: string; // Internal ID string, will map to int 0 for backend
  league_name: string;
  league_description: string;
  league_status: 'active' | 'pending';
  league_start_date: Date;
  club_name?: string;
  location?: string;
  // New fields
  league_duration: number; // Internal number
  group_size: number;
  match_format: 'round-robin' | 'other';
  player_ids: string[]; // Internal usage
}

@Injectable({
  providedIn: 'root'
})
export class AdminService {
  private http = inject(HttpClient);
  private toast = inject(ToastService);
  private confirm = inject(ConfirmService);
  leagueService = inject(LeagueService);

  // Leagues signal
  leagues = signal<League[]>([]);

  constructor() {
    this.fetchLeagues();
  }

  fetchLeagues() {
    this.http.get<any[]>('/api/v1/my_leagues').subscribe({
      next: (data) => {
        const mappedLeagues: League[] = data.map(l => ({
          league_id: String(l.league_id),
          league_name: l.league_name,
          league_description: l.league_description,
          league_status: l.league_status || 'active',
          league_start_date: new Date(l.league_start_date),
          club_name: l.club_name,
          location: l.location,
          league_duration: Number(l.league_duration),
          group_size: l.group_size,
          match_format: l.match_format,
          player_ids: l.players ? l.players.map((p: any) => p.email) : []
        }));
        this.leagues.set(mappedLeagues);
      },
      error: (err) => {
        console.error('Error fetching leagues:', err);
      }
    });
  }

  createLeague(data: Omit<League, 'league_id' | 'league_status'>): Observable<unknown> {
    const newLeague: League = {
      league_id: crypto.randomUUID(),
      league_status: 'pending',
      ...data
    };

    // Optimistic update
    this.leagues.update(current => [newLeague, ...current]);

    // --- Prepare Backend Payload ---

    // 1. Date Formatting (MM-DD-YYYY)
    const startDate = newLeague.league_start_date;
    const mm = String(startDate.getMonth() + 1).padStart(2, '0');
    const dd = String(startDate.getDate()).padStart(2, '0');
    const yyyy = startDate.getFullYear();
    const formattedStartDate = `${mm}-${dd}-${yyyy}`;

    // 2. Calculate End Date
    const endDate = new Date(startDate);
    endDate.setDate(endDate.getDate() + (newLeague.league_duration * 7));
    const endMm = String(endDate.getMonth() + 1).padStart(2, '0');
    const endDd = String(endDate.getDate()).padStart(2, '0');
    const endYyyy = endDate.getFullYear();
    const formattedEndDate = `${endMm}-${endDd}-${endYyyy}`;

    // 3. Map Player IDs to Player Objects
    const allPlayers = this.leagueService.getPlayers()();
    const selectedPlayers = allPlayers.filter(p => newLeague.player_ids.includes(p.id));

    // 4. Construct Payload matching Pydantic Model
    const backendPayload = {
      league_id: 0, // Backend identifies league by name or generates ID
      league_name: newLeague.league_name,
      league_description: newLeague.league_description,
      location: newLeague.location,
      league_start_date: formattedStartDate,
      league_end_date: formattedEndDate,
      league_duration: String(newLeague.league_duration),
      group_size: newLeague.group_size,
      league_status: newLeague.league_status,
      match_format: newLeague.match_format,
      players: selectedPlayers.map(p => ({
        firstName: p.firstName,
        lastName: p.lastName,
        userName: p.userName,
        email: p.email,
        password: p.password || 'temp_pass_123', // Backend requires a password field
        dupr_rating: p.dupr_rating
      }))
    };

    // API Call — caller subscribes and handles success/error UI.
    return this.http.post('/api/v1/league', backendPayload).pipe(
      catchError((err) => {
        // Roll back the optimistic insert so the list matches reality.
        this.leagues.update(current => current.filter(l => l.league_id !== newLeague.league_id));
        return throwError(() => parseHttpError(err));
      })
    );
  }

  async deleteLeague(leagueId: string) {
    const name = this.leagues().find(l => l.league_id === leagueId)?.league_name;
    const confirmed = await this.confirm.ask({
      title: name ? `Delete ${name}?` : 'Delete this league?',
      message:
        'This permanently removes the league along with its groups, schedule, and every recorded match result. This cannot be undone.',
      confirmLabel: 'Delete League',
      cancelLabel: 'Keep League',
    });
    if (!confirmed) return;

    this.leagueService.deleteLeague(leagueId).subscribe({
      next: () => {
        this.leagues.update(current => current.filter(l => l.league_id !== leagueId));
        this.toast.success('League deleted.');
      },
      error: (err) => {
        this.toast.error(parseHttpError(err).message);
      }
    });
  }

  triggerSlotting() {
    console.log('Slotting triggered for current active league');
    return true;
  }
}
