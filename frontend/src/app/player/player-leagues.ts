import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { PlayerService, PlayerLeague } from './player';

@Component({
    selector: 'app-player-leagues',
    standalone: true,
    imports: [CommonModule, RouterLink],
    templateUrl: './player-leagues.html',
    styleUrl: './player-leagues.css'
})
export class PlayerLeaguesComponent implements OnInit {
    playerService = inject(PlayerService);

    allLeagues = this.playerService.getAllLeagues;
    playerLeagues = this.playerService.getLeagues;

    ngOnInit() {
        this.playerService.fetchAllLeagues();
    }

    isRegistered(leagueId: string): boolean {
        return this.playerLeagues().some(l => l.id === leagueId);
    }

    register(leagueId: string) {
        if (confirm('Are you sure you want to register for this league?')) {
            this.playerService.registerForLeague(leagueId).subscribe(success => {
                if (success) {
                    console.log('Successfully registered!');
                } else {
                    console.log('Registration failed. Please try again or contact support.');
                }
            });
        }
    }

    unregister(leagueId: string, leagueName: string) {
        if (confirm(`Are you sure you want to unregister from "${leagueName}"? This cannot be undone.`)) {
            this.playerService.unregisterFromLeague(leagueId).subscribe({
                error: (err) => {
                    const detail = err.error?.detail || err.message || `HTTP ${err.status}`;
                    alert(`Failed to unregister: ${detail}`);
                }
            });
        }
    }

    formatDate(date: Date): string {
        return new Date(date).toLocaleDateString();
    }
}
