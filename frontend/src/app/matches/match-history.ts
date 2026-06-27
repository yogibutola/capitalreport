import { Component, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatchService } from './match';
import { AuthService } from '../auth/auth';

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

  matches = this.matchService.getMatches(this.authService.currentUser()?.id || '');
}
