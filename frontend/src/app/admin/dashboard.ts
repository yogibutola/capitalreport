import { Component, inject, computed } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AdminService } from './admin';

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css'
})
export class DashboardComponent {
  adminService = inject(AdminService);
  leagues = this.adminService.leagues;
  activeLeagueCount = computed(() => this.leagues().filter(l => l.league_status === 'active').length);

  triggerSlotting() {
    if (this.adminService.triggerSlotting()) {
      console.log('Daily slotting triggered successfully! Groups have been updated.');
    }
  }

  deleteLeague(event: Event, leagueId: string) {
    event.stopPropagation();
    this.adminService.deleteLeague(leagueId);
  }
}
