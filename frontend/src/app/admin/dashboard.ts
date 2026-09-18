import { Component, inject, computed, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AdminService } from './admin';
import { TournamentService } from './tournament';
import { AuthService } from '../auth/auth';

/**
 * Club "Manage" tab — an overview hub. The full league and tournament lists live
 * on their own tabs (/admin/leagues, /admin/tournaments); this page shows counts
 * and a short preview of each with links through.
 */
@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css'
})
export class DashboardComponent implements OnInit {
  adminService = inject(AdminService);
  tournamentService = inject(TournamentService);
  auth = inject(AuthService);
  leagues = this.adminService.leagues;
  tournaments = this.tournamentService.tournaments;

  static readonly PREVIEW_SIZE = 3;

  activeLeagueCount = computed(() => this.leagues().filter(l => l.league_status === 'active').length);
  activeTournamentCount = computed(
    () => this.tournaments().filter(t => t.tournament_status === 'active').length
  );

  // Active items first so the hub surfaces what is in play right now.
  leaguePreview = computed(() =>
    [...this.leagues()]
      .sort((a, b) => Number(b.league_status === 'active') - Number(a.league_status === 'active'))
      .slice(0, DashboardComponent.PREVIEW_SIZE)
  );
  tournamentPreview = computed(() =>
    [...this.tournaments()]
      .sort((a, b) => Number(b.tournament_status === 'active') - Number(a.tournament_status === 'active'))
      .slice(0, DashboardComponent.PREVIEW_SIZE)
  );

  ngOnInit() {
    // AdminService is a singleton whose leagues signal is cached from whichever
    // admin was logged in when it was first fetched — refetch on every dashboard
    // visit so switching between clubs doesn't show stale/wrong-club data.
    this.adminService.fetchLeagues();
    this.tournamentService.fetchTournaments();
  }
}
