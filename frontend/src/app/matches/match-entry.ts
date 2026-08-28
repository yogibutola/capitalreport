import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { LeagueService } from '../league/league';
import { MatchService } from './match';
import { AuthService } from '../auth/auth';
import { ErrorListComponent } from '../shared/error-list';

@Component({
  selector: 'app-match-entry',
  standalone: true,
  imports: [FormsModule, RouterLink, ErrorListComponent],
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

  submitAttempted = false;

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

  getCurrentPlayer() {
    return this.players().find(p => p.id === this.currentUserId);
  }

  preventNonIntegerInput(event: KeyboardEvent) {
    if ([46, 8, 9, 27, 13].indexOf(event.keyCode) !== -1 ||
      (event.keyCode === 65 && (event.ctrlKey || event.metaKey)) ||
      (event.keyCode === 67 && (event.ctrlKey || event.metaKey)) ||
      (event.keyCode === 86 && (event.ctrlKey || event.metaKey)) ||
      (event.keyCode === 88 && (event.ctrlKey || event.metaKey)) ||
      (event.keyCode >= 35 && event.keyCode <= 39)) {
      return;
    }
    if ((event.shiftKey || (event.keyCode < 48 || event.keyCode > 57)) && (event.keyCode < 96 || event.keyCode > 105)) {
      event.preventDefault();
    }
  }

  private scoreIsValid(value: number | null): boolean {
    return value !== null && Number.isInteger(value) && value >= 0;
  }

  // Per-field validity, used to highlight inputs after a submit attempt.
  get partnerInvalid() { return !this.partnerId || this.partnerId === this.opponent1Id || this.partnerId === this.opponent2Id; }
  get opponent1Invalid() { return !this.opponent1Id || this.opponent1Id === this.opponent2Id || this.opponent1Id === this.partnerId; }
  get opponent2Invalid() { return !this.opponent2Id || this.opponent1Id === this.opponent2Id || this.opponent2Id === this.partnerId; }
  get myScoreInvalid() { return !this.scoreIsValid(this.myScore); }
  get opponentScoreInvalid() { return !this.scoreIsValid(this.opponentScore); }

  /** Human-readable list of everything wrong, shown in the summary after submit. */
  get errors(): string[] {
    const list: string[] = [];
    if (!this.partnerId) list.push('Choose your partner.');
    if (!this.opponent1Id) list.push('Choose the first opponent.');
    if (!this.opponent2Id) list.push('Choose the second opponent.');

    const picked = [this.partnerId, this.opponent1Id, this.opponent2Id].filter(Boolean);
    if (picked.length > 0 && new Set(picked).size !== picked.length) {
      list.push('Each player can only be picked once — choose three different people.');
    }

    if (!this.scoreIsValid(this.myScore)) list.push('Enter your team’s score as a whole number (0 or more).');
    if (!this.scoreIsValid(this.opponentScore)) list.push('Enter the opponents’ score as a whole number (0 or more).');
    if (this.scoreIsValid(this.myScore) && this.scoreIsValid(this.opponentScore) && this.myScore === this.opponentScore) {
      list.push('A match can’t end in a tie — the two scores must differ.');
    }
    return list;
  }

  isFormValid(): boolean {
    return this.errors.length === 0;
  }

  onSubmit() {
    this.submitAttempted = true;
    if (!this.isFormValid()) return;

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
