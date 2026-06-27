import { Component, inject, computed } from '@angular/core';
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

  stats = computed(() => {
    const userId = this.authService.currentUser()?.id;
    if (userId) {
      return this.statsService.getPlayerStats(userId);
    }
    return null;
  });
}
