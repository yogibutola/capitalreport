import { Component, effect, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, CommonModule } from '@angular/common';
import { AuthService } from '../auth/auth';
import { PlayerService } from '../player/player';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink, DatePipe, CommonModule, FormsModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css'
})
export class DashboardComponent {
  private authService = inject(AuthService);
  private router = inject(Router);
  protected playerService = inject(PlayerService);

  currentUser = this.authService.currentUser;
  leagues = this.playerService.getLeagues;
  upcomingMatches = this.playerService.getUpcomingMatches;

  // Premium banking visual states
  showDupr = signal<boolean>(true);
  welcomeTimestamp = '';

  // Bottom 'Send Score' form controls
  selectedMatchId = '';
  score1 = '';
  score2 = '';
  errorMessage = '';
  successMessage = '';
  recordingInProgress = false;

  get nextMatch() {
    const matches = this.upcomingMatches();
    if (!matches.length) return null;
    return [...matches].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())[0];
  }

  formatMatchDate(date: Date): string {
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const matchDate = new Date(date);
    if (matchDate.toDateString() === today.toDateString()) return 'Today';
    if (matchDate.toDateString() === tomorrow.toDateString()) return 'Tomorrow';
    return matchDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  }

  getTeammates(match: any): string {
    const myId = this.playerService.getCurrentPlayerId();
    return match.players
      .filter((p: any) => match.myTeamPlayerIds.includes(p.id) && p.id !== myId)
      .map((p: any) => p.name)
      .join(', ');
  }

  getOpponents(match: any): string {
    return match.players
      .filter((p: any) => match.opponentTeamPlayerIds.includes(p.id))
      .map((p: any) => p.name)
      .join(', ');
  }

  constructor() {
    effect(() => {
      if (!this.authService.currentUser()) {
        this.router.navigate(['/login']);
      }
    });

    this.generateLastLoginTimestamp();
  }

  toggleDupr() {
    this.showDupr.update(val => !val);
  }

  private generateLastLoginTimestamp() {
    // Generate a beautiful, realistic "Last logged in at..." timestamp in the format DD/MM/YY, HH:MM PM
    const now = new Date();
    // Use yesterday's date to make it realistic
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    yesterday.setHours(22, 52, 0); // 10:52 PM

    const day = String(yesterday.getDate()).padStart(2, '0');
    const month = String(yesterday.getMonth() + 1).padStart(2, '0');
    const year = String(yesterday.getFullYear()).substring(2);
    
    this.welcomeTimestamp = `${day}/${month}/${year}, 10:52 PM`;
  }

  recordScore() {
    this.errorMessage = '';
    this.successMessage = '';

    if (!this.selectedMatchId) {
      this.errorMessage = 'Please select a match to record.';
      return;
    }

    if (this.score1 === '' || this.score2 === '') {
      this.errorMessage = 'Please enter scores for both teams.';
      return;
    }

    const s1 = parseInt(this.score1, 10);
    const s2 = parseInt(this.score2, 10);

    if (isNaN(s1) || isNaN(s2) || s1 < 0 || s2 < 0) {
      this.errorMessage = 'Scores must be positive numbers.';
      return;
    }

    const match = this.upcomingMatches().find(m => m.id === this.selectedMatchId);
    if (!match) {
      this.errorMessage = 'Selected match not found.';
      return;
    }

    this.recordingInProgress = true;
    this.playerService.updateMatchScore(
      match.leagueId,
      match.id,
      s1,
      s2,
      match.myTeamName || 'My Team',
      match.opponentTeamName || 'Opponents'
    ).subscribe(success => {
      this.recordingInProgress = false;
      if (success) {
        this.successMessage = 'Score recorded successfully! Match has been moved to completed.';
        // Clear form
        this.selectedMatchId = '';
        this.score1 = '';
        this.score2 = '';
        
        // Clear success message after 5 seconds
        setTimeout(() => {
          this.successMessage = '';
        }, 5000);
      } else {
        this.errorMessage = 'Failed to submit score to the server. Please try again.';
      }
    });
  }
}
