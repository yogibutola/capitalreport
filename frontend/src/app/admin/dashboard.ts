import { Component, inject, computed, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AdminService } from './admin';
import { TournamentService } from './tournament';
import { ToastService } from '../shared/toast.service';
import { ConfirmService } from '../shared/confirm.service';
import { parseHttpError } from '../shared/http-error';

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
  private toast = inject(ToastService);
  private confirm = inject(ConfirmService);
  leagues = this.adminService.leagues;
  tournaments = this.tournamentService.tournaments;
  activeLeagueCount = computed(() => this.leagues().filter(l => l.league_status === 'active').length);

  ngOnInit() {
    // AdminService is a singleton whose leagues signal is cached from whichever
    // admin was logged in when it was first fetched — refetch on every dashboard
    // visit so switching between clubs doesn't show stale/wrong-club data.
    this.adminService.fetchLeagues();
    this.tournamentService.fetchTournaments();
  }

  async deleteTournament(event: Event, tournamentId: string) {
    event.stopPropagation();
    const confirmed = await this.confirm.ask({
      title: 'Delete this tournament?',
      message:
        'The bracket, seeding, and every recorded result will be permanently deleted. This cannot be undone.',
      confirmLabel: 'Delete Tournament',
      cancelLabel: 'Keep Tournament',
    });
    if (!confirmed) return;
    this.tournamentService.deleteTournament(tournamentId).subscribe({
      next: () => {
        this.tournamentService.fetchTournaments();
        this.toast.success('Tournament deleted.');
      },
      error: (err) => this.toast.error(parseHttpError(err).message),
    });
  }

  deleteLeague(event: Event, leagueId: string) {
    event.stopPropagation();
    this.adminService.deleteLeague(leagueId);
  }
}
