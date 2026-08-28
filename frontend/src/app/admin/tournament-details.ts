import { Component, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';

interface PoolMatch {
  match_id: string;
  participant_one_name?: string;
  participant_two_name?: string;
}

interface Pool {
  pool_id: number;
  pool_name: string;
  players: { firstName: string; lastName: string; dupr_rating?: number }[];
  matches: PoolMatch[];
}

interface KnockoutMatch {
  match_id: string;
  slot_one_label: string;
  slot_two_label: string;
}

interface KnockoutRound {
  round_id: number;
  round_name: string;
  matches: KnockoutMatch[];
}

interface TournamentDetail {
  tournament_id: string;
  tournament_name: string;
  tournament_status?: string;
  tournament_start_date?: string;
  tournament_end_date?: string;
  match_format?: string;
  club_name?: string;
  location?: string;
  pools: Pool[];
  knockout: KnockoutRound[];
}

@Component({
  selector: 'app-tournament-details',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './tournament-details.html',
})
export class TournamentDetailsComponent {
  private http = inject(HttpClient);
  private route = inject(ActivatedRoute);

  tournament = signal<TournamentDetail | null>(null);
  loading = signal(true);
  error = signal('');

  constructor() {
    const id = this.route.snapshot.paramMap.get('tournament_id');
    if (!id) {
      this.error.set('Missing tournament id');
      this.loading.set(false);
      return;
    }
    this.http.get<TournamentDetail>(`/api/v1/tournament/id/${id}`).subscribe({
      next: (data) => {
        this.tournament.set(data);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail || 'Failed to load tournament');
        this.loading.set(false);
      },
    });
  }

  playerName(p: { firstName: string; lastName: string }) {
    return `${p.firstName} ${p.lastName}`.trim();
  }
}
