import { Component, inject, computed, signal, effect } from '@angular/core';
import { RouterLink, Router } from '@angular/router';
import { ThemeService } from '../theme.service';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { PlayerService, UpcomingMatch } from '../player/player';
import { AuthService } from '../auth/auth';
import { GroupsService, GroupEvent } from '../groups/groups.service';

interface UpcomingGroupEvent {
    groupId: string;
    groupName: string;
    event: GroupEvent;
}

interface PlayerResult {
    id: string;
    firstName: string;
    lastName: string;
    email: string;
    dupr_rating: number;
    role: string;
    leagues: { league_name: string }[];
}

@Component({
    selector: 'app-home',
    standalone: true,
    imports: [RouterLink, CommonModule, FormsModule],
    templateUrl: './home.html',
    styleUrl: './home.css'
})

export class HomeComponent {
    private themeService = inject(ThemeService);
    private playerService = inject(PlayerService);
    private router = inject(Router);
    private http = inject(HttpClient);
    private groupsService = inject(GroupsService);
    authService = inject(AuthService);
    currentTheme = this.themeService.theme;

    constructor() {
        effect(() => {
            if (this.authService.currentUser()) {
                this.groupsService.loadGroupsForCurrentUser();
            }
        });
    }

    // Player search state
    searchFirstName = '';
    searchLastName = '';
    searchResults = signal<PlayerResult[]>([]);
    allPlayers = signal<PlayerResult[]>([]);
    isSearching = signal(false);
    searchError = signal<string | null>(null);
    hasSearched = signal(false);

    searchPlayers(): void {
        const first = this.searchFirstName.trim().toLowerCase();
        const last = this.searchLastName.trim().toLowerCase();
        if (!first && !last) return;

        this.isSearching.set(true);
        this.searchError.set(null);
        this.hasSearched.set(true);

        if (this.allPlayers().length > 0) {
            this.filterPlayers(first, last);
            this.isSearching.set(false);
            return;
        }

        this.http.get<PlayerResult[]>('api/v1/players').subscribe({
            next: (players) => {
                this.allPlayers.set(players);
                this.filterPlayers(first, last);
                this.isSearching.set(false);
            },
            error: () => {
                this.searchError.set('Unable to fetch players. Please try again.');
                this.isSearching.set(false);
            }
        });
    }

    private filterPlayers(first: string, last: string): void {
        const filtered = this.allPlayers().filter(p => {
            const firstMatch = !first || p.firstName.toLowerCase().includes(first);
            const lastMatch = !last || p.lastName.toLowerCase().includes(last);
            return firstMatch && lastMatch;
        });
        this.searchResults.set(filtered);
    }

    clearSearch(): void {
        this.searchFirstName = '';
        this.searchLastName = '';
        this.searchResults.set([]);
        this.hasSearched.set(false);
        this.searchError.set(null);
    }

    nextMatch = computed<UpcomingMatch | null>(() => {
        const matches = this.playerService.getUpcomingMatches();
        if (!matches.length) return null;
        return [...matches].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())[0];
    });

    goToPlayerDashboard() {
        this.router.navigate(['/player']);
    }

    upcomingEvents = computed<UpcomingGroupEvent[]>(() => {
        const now = new Date();
        const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
        const items: UpcomingGroupEvent[] = [];
        for (const group of this.groupsService.groups()) {
            for (const event of group.events ?? []) {
                if (event.date >= todayStr) {
                    items.push({ groupId: group.group_id, groupName: group.name, event });
                }
            }
        }
        items.sort((a, b) =>
            (a.event.date + (a.event.time ?? '')).localeCompare(b.event.date + (b.event.time ?? '')));
        return items.slice(0, 3);
    });

    goToGroups() {
        this.router.navigate(['/groups']);
    }

    formatEventDate(dateStr: string): string {
        const [y, m, d] = dateStr.split('-').map(Number);
        if (!y || !m || !d) return dateStr;
        return this.formatMatchDate(new Date(y, m - 1, d));
    }

    formatEventTime(time: string): string {
        const [h, m] = time.split(':').map(Number);
        if (isNaN(h) || isNaN(m)) return time;
        const suffix = h >= 12 ? 'PM' : 'AM';
        const hour12 = h % 12 === 0 ? 12 : h % 12;
        return `${hour12}:${String(m).padStart(2, '0')} ${suffix}`;
    }

    inCount(event: GroupEvent): number {
        return (event.votes ?? []).filter(v => v.vote === 'In').length;
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
