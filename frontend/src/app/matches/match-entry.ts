import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { LeagueService } from '../league/league';
import { MatchService } from './match';
import { AuthService } from '../auth/auth';

@Component({
  selector: 'app-match-entry',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './match-entry.html',
  styleUrl: './match-entry.css'
})
export class MatchEntryComponent {
  leagueService = inject(LeagueService);
  matchService = inject(MatchService);
  authService = inject(AuthService);
  router = inject(Router);

  players = this.leagueService.getPlayers();
  currentUserId = this.authService.currentUser()?.id;

  partnerId = '';
  opponent1Id = '';
  opponent2Id = '';
  myScore: number | null = null;
  opponentScore: number | null = null;

  // Current date and time for display
  currentDate = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });

  currentTime = new Date().toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit'
  });

  // Get current player info
  getCurrentPlayer() {
    return this.players().find(p => p.id === this.currentUserId);
  }

  // Prevent non-integer input
  preventNonIntegerInput(event: KeyboardEvent) {
    // Allow: Backspace, Delete, Tab, Escape, Enter
    if ([46, 8, 9, 27, 13].indexOf(event.keyCode) !== -1 ||
      // Allow: Ctrl+A
      (event.keyCode === 65 && (event.ctrlKey || event.metaKey)) ||
      // Allow: Ctrl+C
      (event.keyCode === 67 && (event.ctrlKey || event.metaKey)) ||
      // Allow: Ctrl+V
      (event.keyCode === 86 && (event.ctrlKey || event.metaKey)) ||
      // Allow: Ctrl+X
      (event.keyCode === 88 && (event.ctrlKey || event.metaKey)) ||
      // Allow: home, end, left, right
      (event.keyCode >= 35 && event.keyCode <= 39)) {
      // let it happen, don't do anything
      return;
    }
    // Ensure that it is a number and stop the keypress
    if ((event.shiftKey || (event.keyCode < 48 || event.keyCode > 57)) && (event.keyCode < 96 || event.keyCode > 105)) {
      event.preventDefault();
    }
  }

  // Form validation
  isFormValid(): boolean {
    return !!(
      this.partnerId &&
      this.opponent1Id &&
      this.opponent2Id &&
      this.myScore !== null &&
      this.opponentScore !== null &&
      Number.isInteger(this.myScore) &&
      this.myScore >= 0 &&
      Number.isInteger(this.opponentScore) &&
      this.opponentScore >= 0 &&
      this.partnerId !== this.opponent1Id &&
      this.partnerId !== this.opponent2Id &&
      this.opponent1Id !== this.opponent2Id
    );
  }

  onSubmit() {
    if (this.isFormValid()) {
      this.matchService.addMatch({
        id: crypto.randomUUID(),
        date: new Date(),
        players: [this.currentUserId!, this.partnerId, this.opponent1Id, this.opponent2Id],
        scores: [this.myScore!, this.opponentScore!],
        winnerTeam: this.myScore! > this.opponentScore! ? 1 : 2
      });
      this.router.navigate(['/player']);
    }
  }
}
