import { Component, inject, computed } from '@angular/core';
import { RouterLink, Router } from '@angular/router';
import { ThemeService } from '../theme.service';
import { CommonModule } from '@angular/common';
import { PlayerService, UpcomingMatch } from '../player/player';
import { AuthService } from '../auth/auth';

@Component({
    selector: 'app-home',
    standalone: true,
    imports: [RouterLink, CommonModule],
    templateUrl: './home.html',
    styleUrl: './home.css'
})
export class HomeComponent {
    private themeService = inject(ThemeService);
    private playerService = inject(PlayerService);
    private router = inject(Router);
    authService = inject(AuthService);
    currentTheme = this.themeService.theme;

    nextMatch = computed<UpcomingMatch | null>(() => {
        const matches = this.playerService.getUpcomingMatches();
        if (!matches.length) return null;
        return [...matches].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())[0];
    });

    goToPlayerDashboard() {
        this.router.navigate(['/player']);
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

    getTeammates(match: UpcomingMatch): string {
        const myId = this.playerService.getCurrentPlayerId();
        return match.players
            .filter(p => match.myTeamPlayerIds.includes(p.id) && p.id !== myId)
            .map(p => p.name)
            .join(', ');
    }

    getOpponents(match: UpcomingMatch): string {
        return match.players
            .filter(p => match.opponentTeamPlayerIds.includes(p.id))
            .map(p => p.name)
            .join(', ');
    }

    images = [
        {
            src: '/assets/images/pickleball_group_high_five_1767668502686.png',
            alt: 'Group high five',
            title: 'Manage Your League',
            caption: 'Effortless organization for clubs and groups.',
            buttonText: 'Manage League',
            link: '/admin/login'
        },
        {
            src: '/assets/images/pickleball_serve_moment_1767668489237.png',
            alt: 'Close up of a serve',
            title: 'Player Portal',
            caption: 'Track your stats, matches, and ratings.',
            buttonText: 'Player Sign-In',
            link: '/login'
        },
        {
            src: '/assets/images/pickleball_game_action_1767668476539.png',
            alt: 'Action shot of a doubles game',
            title: 'See It in Action',
            caption: 'Experience the power of automated slotting.',
            buttonText: 'Demo',
            link: '/signup'
        }
    ];

    currentSlide = 0;

    nextSlide() {
        this.currentSlide = (this.currentSlide + 1) % this.images.length;
    }

    prevSlide() {
        this.currentSlide = (this.currentSlide - 1 + this.images.length) % this.images.length;
    }

    setSlide(index: number) {
        this.currentSlide = index;
    }
}
