import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { PlayerService } from './player';
import { ToastService } from '../shared/toast.service';
import { ConfirmService } from '../shared/confirm.service';
import { parseHttpError } from '../shared/http-error';

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
    private toast = inject(ToastService);
    private confirm = inject(ConfirmService);

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

    async register(leagueId: string) {
        const confirmed = await this.confirm.ask({
            title: 'Register for this league?',
            message:
                'You will be added to the player roster and included in the scheduling for the next round.',
            confirmLabel: 'Register',
            cancelLabel: 'Not Now',
            tone: 'primary',
        });
        if (!confirmed) return;

        this.playerService.registerForLeague(leagueId).subscribe(success => {
            if (success) {
                this.toast.success("You're registered for this league.");
            } else {
                this.toast.error("We couldn't complete your registration. Please try again or contact support.");
            }
        });
    }

    async unregister(leagueId: string, leagueName: string) {
        const confirmed = await this.confirm.ask({
            title: `Unregister from ${leagueName}?`,
            message:
                'You will be removed from the roster and your current group placement. Rejoining later starts you over from scratch. This cannot be undone.',
            confirmLabel: 'Unregister',
            cancelLabel: 'Stay Registered',
        });
        if (!confirmed) return;

        this.playerService.unregisterFromLeague(leagueId).subscribe({
            next: () => this.toast.success(`You've been unregistered from "${leagueName}".`),
            error: (err) => this.toast.error(parseHttpError(err).message)
        });
    }

    formatDate(date: Date): string {
        return new Date(date).toLocaleDateString();
    }
}
