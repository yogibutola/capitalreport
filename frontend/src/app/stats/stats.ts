import { Injectable, inject } from '@angular/core';
import { MatchService } from '../matches/match';
import { LeagueService } from '../league/league';

export interface PlayerStats {
  totalMatches: number;
  wins: number;
  losses: number;
  winRate: number;
  bestPartner: string | null; // Name of best partner
}

@Injectable({
  providedIn: 'root'
})
export class StatsService {
  private matchService = inject(MatchService);
  private leagueService = inject(LeagueService);

  getPlayerStats(userId: string): PlayerStats {
    const matches = this.matchService.getMatches(userId)(); // Access signal value
    const playerMatches = matches.filter(m => m.players.includes(userId));

    let wins = 0;
    const partnerWins = new Map<string, number>();

    playerMatches.forEach(match => {
      // userId is in match.players [0,1,2,3]. Teams are [0,1] vs [2,3]
      const team1 = [match.players[0], match.players[1]];
      const team2 = [match.players[2], match.players[3]];

      const myTeam = team1.includes(userId) ? 1 : 2;
      const won = match.winnerTeam === myTeam;

      if (won) {
        wins++;
        // Find partner
        const team = myTeam === 1 ? team1 : team2;
        const partnerId = team.find(id => id !== userId);
        if (partnerId) {
          partnerWins.set(partnerId, (partnerWins.get(partnerId) || 0) + 1);
        }
      }
    });

    // Find best partner
    let bestPartnerId: string | null = null;
    let maxWins = 0;
    partnerWins.forEach((count, id) => {
      if (count > maxWins) {
        maxWins = count;
        bestPartnerId = id;
      }
    });

    const bestPartnerName = bestPartnerId
      ? this.leagueService.getPlayers()().find(p => p.id === bestPartnerId)?.name || 'Unknown'
      : null;

    return {
      totalMatches: playerMatches.length,
      wins,
      losses: playerMatches.length - wins,
      winRate: playerMatches.length > 0 ? (wins / playerMatches.length) * 100 : 0,
      bestPartner: bestPartnerName
    };
  }
}
