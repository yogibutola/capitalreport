import { Component, inject, computed, effect } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatchService } from './match';
import { AuthService } from '../auth/auth';

interface MatchRow {
  matchId: string;
  sourceLabel: string;
  teamOneName: string;
  teamTwoName: string;
  scoreOne: number;
  scoreTwo: number;
  winner: 0 | 1 | 2;
  time: string | Date | null;
  location: string | null;
  matchStatus: string;
}

@Component({
  selector: 'app-match-history',
  standalone: true,
  imports: [DatePipe, RouterLink],
  templateUrl: './match-history.html',
  styleUrl: './match-history.css'
})
export class MatchHistoryComponent {
  matchService = inject(MatchService);
  authService = inject(AuthService);

  constructor() {
    // Load league + tournament matches for the logged-in player
    effect(() => {
      const email = this.authService.currentUser()?.email;
      if (email) {
        this.matchService.loadMatchesForPlayer(email);
      }
    });
  }

  matches = computed<MatchRow[]>(() => {
    const raw = this.matchService.getMatches()();
    return raw.filter(m => m.team_one && m.team_two).map(m => this.toRow(m));
  });

  private toRow(m: any): MatchRow {
    const t1 = m.team_one;
    const t2 = m.team_two;

    const s1 = Number(t1.score || 0);
    const s2 = Number(t2.score || 0);
    const statusLower = String(m.match_status || '').toLowerCase();
    const isDecided = statusLower === 'completed' || statusLower === 'bye';
    const winner: 0 | 1 | 2 = isDecided ? (s1 > s2 ? 1 : s2 > s1 ? 2 : 0) : 0;

    return {
      matchId: m.match_id || `${m.source}-${m.league_id || m.tournament_id}-${m.round_id ?? m.stage}-${t1.team_name}-${t2.team_name}`,
      sourceLabel: m.source === 'tournament' ? (m.tournament_name || 'Tournament') : (m.league_name || 'League'),
      teamOneName: t1.team_name || 'TBD',
      teamTwoName: t2.team_name || 'TBD',
      scoreOne: s1,
      scoreTwo: s2,
      winner,
      time: m.time || null,
      location: m.location || null,
      matchStatus: m.match_status || ''
    };
  }
}
