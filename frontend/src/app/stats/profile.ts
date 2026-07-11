import { Component, inject, computed, effect } from '@angular/core';
import { RouterLink } from '@angular/router';
import { StatsService } from './stats';
import { AuthService } from '../auth/auth';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './profile.html',
  styleUrl: './profile.css'
})
export class ProfileComponent {
  statsService = inject(StatsService);
  authService = inject(AuthService);

  constructor() {
    // Load matches from all leagues for the logged-in player
    effect(() => {
      const email = this.authService.currentUser()?.email;
      if (email) {
        this.statsService.loadMatchesForPlayer(email);
      }
    });
  }

  stats = computed(() => {
    const email = this.authService.currentUser()?.email;
    if (email) {
      return this.statsService.getPlayerStats(email);
    }
    return null;
  });
}
