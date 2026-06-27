import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AdminService } from './admin';

@Component({
  selector: 'app-create-league',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './create-league.html',
  styleUrl: './create-league.css'
})
export class CreateLeagueComponent {
  adminService = inject(AdminService);
  router = inject(Router);

  constructor() {
    this.adminService.leagueService.fetchPlayers();
  }

  allPlayers = this.adminService.leagueService.getPlayers();

  // Form Model
  name = '';
  startDate = '';
  durationWeeks = 10;
  groupSize = 5;
  format: 'round-robin' | 'other' = 'round-robin';
  selectedPlayerIds = new Set<string>();

  togglePlayer(id: string) {
    if (this.selectedPlayerIds.has(id)) {
      this.selectedPlayerIds.delete(id);
    } else {
      this.selectedPlayerIds.add(id);
    }
  }

  onSubmit() {
    if (this.name && this.startDate) {
      this.adminService.createLeague({
        league_name: this.name,
        league_description: this.name, // Using name as description for now
        league_start_date: new Date(this.startDate),
        league_duration: this.durationWeeks,
        group_size: this.groupSize,
        match_format: this.format,
        player_ids: Array.from(this.selectedPlayerIds)
      });
      this.router.navigate(['/admin']);
    }
  }
}
