import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { catchError } from 'rxjs/operators';
import { of } from 'rxjs';

// Legacy locally-logged match shape, still used by MatchEntryComponent's
// (unwired) quick-add form. Real match history comes from the backend as
// the league/tournament Match shape (team_one/team_two/...), typed loosely
// below since the two shapes don't overlap.
export interface Match {
  id: string;
  date: Date;
  players: string[]; // IDs of 4 players
  scores: number[]; // [Team1Score, Team2Score]
  winnerTeam: number; // 1 or 2
}

@Injectable({
  providedIn: 'root'
})
export class MatchService {
  private http = inject(HttpClient);

  // All matches for the player, across leagues and tournaments
  private matches = signal<any[]>([]);
  private loadedForEmail: string | null = null;

  /** Fetch all matches for a player across leagues and tournaments (cached per email). */
  loadMatchesForPlayer(email: string) {
    const emailLower = email.toLowerCase();
    if (this.loadedForEmail === emailLower) return;
    this.loadedForEmail = emailLower;

    this.http.get<any[]>(`api/v1/player/${encodeURIComponent(emailLower)}/matches`).pipe(
      catchError(err => {
        console.error('[MatchService] Error fetching player matches:', err);
        return of([]);
      })
    ).subscribe(matches => {
      this.matches.set(Array.isArray(matches) ? matches : []);
    });
  }

  getMatches() {
    return this.matches;
  }

  addMatch(match: Match) {
    this.matches.update(current => [match, ...current]);
  }
}
