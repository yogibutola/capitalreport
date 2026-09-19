import { Component, inject, computed, effect, signal, PLATFORM_ID } from '@angular/core';
import { RouterLink, Router } from '@angular/router';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { PlayerService, UpcomingMatch } from '../player/player';
import { AuthService } from '../auth/auth';
import { GroupsService, GroupEvent } from '../groups/groups.service';
import { ToastService } from '../shared/toast.service';
import { parseHttpError } from '../shared/http-error';
import { SmartSlottingDemoComponent } from './smart-slotting-demo';
import { RevealDirective } from './reveal.directive';
import { BrandLogoComponent } from '../shared/brand-logo';
import { BrandMarkComponent } from '../shared/brand-mark';
import { ThemeToggleComponent } from '../shared/theme-toggle';

interface UpcomingGroupEvent {
    groupId: string;
    groupName: string;
    event: GroupEvent;
}

// TODO(content): standings, seasons, bracket and the testimonial
// are placeholder marketing data — swap for real numbers/quotes before launch.
const STANDINGS = [
    { team: 'Dink Dynasty', w: 11, l: 1, pts: 33, diff: '+64', lead: true },
    { team: 'Net Ninjas', w: 9, l: 3, pts: 27, diff: '+41', lead: false },
    { team: 'Kitchen Sync', w: 8, l: 4, pts: 24, diff: '+22', lead: false },
    { team: 'Third Shot Pros', w: 6, l: 6, pts: 18, diff: '-5', lead: false },
    { team: 'Paddle Batts', w: 4, l: 8, pts: 12, diff: '-31', lead: false },
];

const SEASONS = [
    { name: 'Spring 4.0 Division', meta: '24 players · 12 teams', pct: 75, status: 'Week 6 / 8', tone: 'good' },
    { name: 'Ladder · 3.5 & under', meta: '38 players', pct: 50, status: 'Week 3 / 6', tone: 'muted' },
    { name: 'Summer Mixed Doubles', meta: '18 teams', pct: 0, status: 'Starts Mon', tone: 'coral' },
];

interface BracketMatch {
    top: { seed: number; name: string; win: boolean };
    bot: { seed: number; name: string; win: boolean };
    score: string;
    live?: boolean;
}

const BRACKET: { round: string; matches: BracketMatch[] }[] = [
    {
        round: 'Quarters',
        matches: [
            { top: { seed: 1, name: 'Dink Dynasty', win: true }, bot: { seed: 8, name: 'Paddle Batts', win: false }, score: '11 · 4 · 11' },
            { top: { seed: 4, name: 'Third Shot Pros', win: false }, bot: { seed: 5, name: 'Lob Squad', win: true }, score: '9 · 11 · 8' },
            { top: { seed: 2, name: 'Net Ninjas', win: true }, bot: { seed: 7, name: 'Erne Gang', win: false }, score: '11 · 11' },
            { top: { seed: 3, name: 'Kitchen Sync', win: true }, bot: { seed: 6, name: 'Drop Shots', win: false }, score: '11 · 9 · 11' },
        ],
    },
    {
        round: 'Semis',
        matches: [
            { top: { seed: 1, name: 'Dink Dynasty', win: true }, bot: { seed: 5, name: 'Lob Squad', win: false }, score: '11 · 7 · 11' },
            { top: { seed: 2, name: 'Net Ninjas', win: false }, bot: { seed: 3, name: 'Kitchen Sync', win: false }, score: '11 · 9 · —', live: true },
        ],
    },
    {
        round: 'Final',
        matches: [
            { top: { seed: 1, name: 'Dink Dynasty', win: false }, bot: { seed: 0, name: 'TBD', win: false }, score: 'Court 1 · 7:40' },
        ],
    },
];

const MINI_FEATURES = [
    {
        title: 'Court & time booking',
        body: 'Members grab open courts from their phone; league nights block off automatically.',
        icon: 'calendar',
    },
    {
        title: 'Payments & dues',
        body: 'Season fees, drop-in passes and tournament entries, collected and reconciled for you.',
        icon: 'card',
    },
    {
        title: 'Player messaging',
        body: 'Match reminders and roster notices in English, Spanish, Chinese and Korean.',
        icon: 'chat',
    },
];

@Component({
    selector: 'app-home',
    standalone: true,
    imports: [RouterLink, CommonModule, SmartSlottingDemoComponent, RevealDirective, BrandLogoComponent, BrandMarkComponent, ThemeToggleComponent],
    templateUrl: './home.html',
    styleUrl: './home.css'
})
export class HomeComponent {
    private playerService = inject(PlayerService);
    private router = inject(Router);
    private groupsService = inject(GroupsService);
    private toast = inject(ToastService);
    private platformId = inject(PLATFORM_ID);
    authService = inject(AuthService);

    readonly standings = STANDINGS;
    readonly seasons = SEASONS;
    readonly bracket = BRACKET;
    readonly miniFeatures = MINI_FEATURES;

    /** Which demo (if any) is currently signing in — disables every demo CTA. */
    demoLoading = signal<'admin' | 'player' | null>(null);
    menuOpen = signal(false);

    constructor() {
        effect(() => {
            if (this.authService.currentUser()) {
                this.groupsService.loadGroupsForCurrentUser();
            }
        });
    }

    toggleMenu() {
        this.menuOpen.update(v => !v);
    }

    closeMenu() {
        this.menuOpen.set(false);
    }

    scrollTo(id: string, event?: Event) {
        event?.preventDefault();
        this.closeMenu();
        if (!isPlatformBrowser(this.platformId)) return;
        const target = document.getElementById(id);
        if (!target) return;
        const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        target.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
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

    // "Book a demo" CTAs are routerLinks to /book-demo (BookDemoComponent);
    // the in-section "See it in a demo" links launch the instant read-only club demo.
    startAdminDemo() {
        this.startDemo('admin', '/admin/leagues');
    }

    startPlayerDemo() {
        this.startDemo('player', '/player');
    }

    private startDemo(persona: 'admin' | 'player', target: string) {
        if (this.demoLoading()) return;
        this.closeMenu();
        this.demoLoading.set(persona);
        this.authService.demoSignin(persona).subscribe({
            next: () => {
                this.demoLoading.set(null);
                this.router.navigateByUrl(target);
            },
            error: (err) => {
                this.demoLoading.set(null);
                this.toast.error(parseHttpError(err).message);
            }
        });
    }
}
