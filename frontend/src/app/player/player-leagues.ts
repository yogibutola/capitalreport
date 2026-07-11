import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { PlayerService } from './player';

@Component({
    selector: 'app-player-leagues',
    standalone: true,
    imports: [CommonModule, RouterLink],
    templateUrl: './player-leagues.html',
    styleUrl: './player-leagues.css'
})
export class PlayerLeaguesComponent implements OnInit {
    playerService = inject(PlayerService);
    router = inject(Router);
    route = inject(ActivatedRoute);

    playerLeagues = this.playerService.getLeagues;
    availableLeagues = this.playerService.getAvailableLeagues;

    activeTab = signal<'my' | 'available'>('my');

    ngOnInit() {
        this.playerService.fetchAllLeagues();
        if (this.route.snapshot.queryParamMap.get('tab') === 'available') {
            this.activeTab.set('available');
        }
    }

    viewLeague(leagueId: string) {
        this.playerService.selectLeague(leagueId);
        this.router.navigate(['/player'], { queryParams: { section: 'league-details' } });
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
