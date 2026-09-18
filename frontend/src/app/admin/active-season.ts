import { Component, OnInit, computed, effect, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { AdminService, League } from './admin';
import { TournamentService, TournamentSummary } from './tournament';
import {
  isActiveStatus,
  summarizeLeague,
  LeagueDetailsWithMatches,
  LeagueProgress,
} from './season-progress';

export { isActiveStatus, summarizeLeague };
export type { LeagueProgress };

@Component({
  selector: 'app-active-season',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './active-season.html',
  styleUrl: './active-season.css',
})
export class ActiveSeasonComponent implements OnInit {
  private adminService = inject(AdminService);
  private tournamentService = inject(TournamentService);
  private http = inject(HttpClient);

  activeLeagues = computed<League[]>(() =>
    this.adminService.leagues().filter((l) => isActiveStatus(l.league_status))
  );
  activeTournaments = computed<TournamentSummary[]>(() =>
    this.tournamentService.tournaments().filter((t) => isActiveStatus(t.tournament_status))
  );

  /** Progress keyed by league_id; absent until the detail fetch lands. */
  progress = signal<Record<string, LeagueProgress>>({});
  /** league_ids whose detail fetch failed. */
  progressErrors = signal<Record<string, true>>({});
  private requested = new Set<string>();

  playersInPlay = computed(() =>
    Object.values(this.progress()).reduce((sum, p) => sum + p.playerCount, 0)
  );
  matchesPending = computed(() =>
    Object.values(this.progress()).reduce((sum, p) => sum + p.matchesPending, 0)
  );
  hasActivity = computed(() => this.activeLeagues().length > 0 || this.activeTournaments().length > 0);

  constructor() {
    // Fetch the full payload for each active league once we know which ones exist.
    effect(() => {
      for (const league of this.activeLeagues()) {
        if (this.requested.has(league.league_id)) continue;
        this.requested.add(league.league_id);
        this.fetchProgress(league);
      }
    });
  }

  ngOnInit() {
    // AdminService/TournamentService cache per singleton — refetch so switching
    // clubs never shows another club's season.
    this.adminService.fetchLeagues();
    this.tournamentService.fetchTournaments();
  }

  progressFor(league: League): LeagueProgress | undefined {
    return this.progress()[league.league_id];
  }

  private fetchProgress(league: League) {
    this.http
      .get<LeagueDetailsWithMatches>(`/api/v1/league/name/${encodeURIComponent(league.league_name)}`)
      .subscribe({
        next: (data) => {
          const summary = summarizeLeague(data ?? {});
          this.progress.update((m) => ({ ...m, [league.league_id]: summary }));
        },
        error: (err) => {
          console.error('Error fetching league progress:', err);
          this.progressErrors.update((m) => ({ ...m, [league.league_id]: true }));
        },
      });
  }
}
