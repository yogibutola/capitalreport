import { Component, inject, computed, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AdminService } from './admin';
import { AuthService } from '../auth/auth';

/**
 * Club "Leagues" tab — lists every league the club owns with create/delete actions.
 * Split out of the Manage dashboard so leagues and tournaments each get a full page.
 */
@Component({
  selector: 'app-admin-leagues',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './leagues.html',
  styleUrl: './dashboard.css'
})
export class LeaguesComponent implements OnInit {
  adminService = inject(AdminService);
  auth = inject(AuthService);
  leagues = this.adminService.leagues;
  activeLeagueCount = computed(() => this.leagues().filter(l => l.league_status === 'active').length);

  ngOnInit() {
    // AdminService caches leagues from whichever club fetched first — refetch on
    // every visit so switching clubs never shows another club's leagues.
    this.adminService.fetchLeagues();
  }

  deleteLeague(event: Event, leagueId: string) {
    event.stopPropagation();
    this.adminService.deleteLeague(leagueId);
  }
}
