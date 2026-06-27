import { Injectable, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { LeagueService } from '../league/league';

export interface League {
  league_id: string; // Internal ID string, will map to int 0 for backend
  league_name: string;
  league_description: string;
  league_status: 'active' | 'pending';
  league_start_date: Date;
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
  leagueService = inject(LeagueService);

  // Leagues signal
  leagues = signal<League[]>([]);

  constructor() {
    this.fetchLeagues();
  }

  fetchLeagues() {
    this.http.get<any[]>('/api/v1/all_leagues').subscribe({
      next: (data) => {
        const mappedLeagues: League[] = data.map(l => ({
          league_id: String(l.league_id),
          league_name: l.league_name,
          league_description: l.league_description,
          league_status: l.league_status || 'active',
          league_start_date: new Date(l.league_start_date),
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

  createLeague(data: Omit<League, 'league_id' | 'league_status'>) {
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

    // API Call
    console.log('Sending payload:', backendPayload);
    this.http.post('/api/v1/league', backendPayload).subscribe({
      next: (response) => console.log('League created successfully', response),
      error: (err) => {
        console.error('Error creating league', err);
        console.log('Error creating league: ' + (err.error?.detail));
        console.log('Error creating league: ' + (err.statusText));
        console.log('Error creating league: ' + (JSON.stringify(err.error)));

      }
    });
  }

  deleteLeague(leagueId: string) {
    if (confirm('Are you sure you want to delete this league? This action cannot be undone.')) {
      this.leagueService.deleteLeague(leagueId).subscribe({
        next: () => {
          this.leagues.update(current => current.filter(l => l.league_id !== leagueId));
          console.log('League deleted successfully.');
        },
        error: (err) => {
          console.error('Error deleting league', err);
          console.log('Failed to delete league: ' + (err.error?.detail || err.statusText));
        }
      });
    }
  }

  triggerSlotting() {
    console.log('Slotting triggered for current active league');
    return true;
  }
}
