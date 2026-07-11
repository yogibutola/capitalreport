import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { catchError } from 'rxjs/operators';
import { of } from 'rxjs';

export interface PlayerStats {
  totalMatches: number;
  wins: number;
  losses: number;
  winRate: number;
  bestPartner: string | null; // Name of best partner
  leaguesPlayed: number;
}

@Injectable({
  providedIn: 'root'
})
export class StatsService {
  private http = inject(HttpClient);

  // All matches for the player, across all leagues
  private matches = signal<any[]>([]);
  private loadedForEmail: string | null = null;

  /** Fetch all matches for a player across all leagues (cached per email). */
  loadMatchesForPlayer(email: string) {
    const emailLower = email.toLowerCase();
    if (this.loadedForEmail === emailLower) return;
    this.loadedForEmail = emailLower;

    this.http.get<any[]>(`api/v1/player/${encodeURIComponent(emailLower)}/matches`).pipe(
      catchError(err => {
        console.error('[StatsService] Error fetching player matches:', err);
        return of([]);
      })
    ).subscribe(matches => {
      this.matches.set(Array.isArray(matches) ? matches : []);
    });
  }

  getPlayerStats(email: string): PlayerStats {
    const emailLower = email.toLowerCase();
    const allMatches = this.matches();

    let wins = 0;
    let completed = 0;
    const leagueIds = new Set<string>();
    const partnerWins = new Map<string, { name: string; wins: number }>();

    const playerEmail = (p: any) => (p?.email || '').toLowerCase();
    const playerName = (p: any) =>
      p?.name || (p?.firstName ? `${p.firstName} ${p.lastName}` : (p?.email || 'Unknown'));

    allMatches.forEach(m => {
      const t1 = m.team_one || m.team1;
      const t2 = m.team_two || m.team2;
      if (!t1 || !t2) return;

      if (m.league_id) leagueIds.add(String(m.league_id));

      const s1 = Number(t1.score || 0);
      const s2 = Number(t2.score || 0);
      const statusLower = String(m.match_status || '').toLowerCase();
      const isCompleted = statusLower === 'completed' || statusLower === 'finished' || s1 > 0 || s2 > 0;
      if (!isCompleted) return;

      const team1Players = [t1.player_one || t1.player1, t1.player_two || t1.player2];
      const team2Players = [t2.player_one || t2.player1, t2.player_two || t2.player2];

      const isTeam1 = team1Players.some(p => playerEmail(p) === emailLower);
      const isTeam2 = team2Players.some(p => playerEmail(p) === emailLower);
      if (!isTeam1 && !isTeam2) return;

      completed++;
      const won = isTeam1 ? s1 > s2 : s2 > s1;

      if (won) {
        wins++;
        const myTeam = isTeam1 ? team1Players : team2Players;
        const partner = myTeam.find(p => p && playerEmail(p) !== emailLower);
        if (partner) {
          const key = playerEmail(partner);
          const entry = partnerWins.get(key) || { name: playerName(partner), wins: 0 };
          entry.wins++;
          partnerWins.set(key, entry);
        }
      }
    });

    let bestPartner: string | null = null;
    let maxWins = 0;
    partnerWins.forEach(entry => {
      if (entry.wins > maxWins) {
        maxWins = entry.wins;
        bestPartner = entry.name;
      }
    });

    return {
      totalMatches: completed,
      wins,
      losses: completed - wins,
      winRate: completed > 0 ? (wins / completed) * 100 : 0,
      bestPartner,
      leaguesPlayed: leagueIds.size
    };
  }
}
