import { Injectable, signal } from '@angular/core';

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
  private matches = signal<Match[]>([]);

  getMatches(userId: string) {
    // Return all matches where user is present
    // For mock, just return all or filter
    return this.matches;
  }

  addMatch(match: Match) {
    this.matches.update(current => [match, ...current]);
  }
}
