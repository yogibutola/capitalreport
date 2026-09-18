import { Component, inject, computed, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TournamentService } from './tournament';
import { AuthService } from '../auth/auth';
import { ToastService } from '../shared/toast.service';
import { ConfirmService } from '../shared/confirm.service';
import { parseHttpError } from '../shared/http-error';

/**
 * Club "Tournaments" tab — lists every tournament the club owns with create/delete actions.
 * Split out of the Manage dashboard so leagues and tournaments each get a full page.
 */
@Component({
  selector: 'app-admin-tournaments',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './tournaments.html',
  styleUrl: './dashboard.css'
})
export class TournamentsComponent implements OnInit {
  tournamentService = inject(TournamentService);
  auth = inject(AuthService);
  private toast = inject(ToastService);
  private confirm = inject(ConfirmService);
  tournaments = this.tournamentService.tournaments;
  activeTournamentCount = computed(
    () => this.tournaments().filter(t => t.tournament_status === 'active').length
  );

  ngOnInit() {
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
}
