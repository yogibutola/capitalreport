import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { PlayerService, UpcomingMatch, PlayerStanding } from './player';
import { AuthService } from '../auth/auth';
import { ToastService } from '../shared/toast.service';

@Component({
    selector: 'app-player-dashboard',
    standalone: true,
    imports: [CommonModule, RouterLink],
    templateUrl: './player-dashboard.html',
    styleUrl: './player-dashboard.css'
})
export class PlayerDashboardComponent {
    playerService = inject(PlayerService);
    authService = inject(AuthService);
    router = inject(Router);
    route = inject(ActivatedRoute);
    private toast = inject(ToastService);

    constructor() {
        // Allow deep-linking to a specific section (e.g. from the Leagues page)
        const section = this.route.snapshot.queryParamMap.get('section');
        if (section === 'stats' || section === 'league-details' || section === 'matches') {
            this.activeSection.set(section);
        }
    }

    leagues = this.playerService.getLeagues;
    selectedLeague = this.playerService.getSelectedLeague;
    upcomingMatches = this.playerService.getUpcomingMatches;
    completedMatches = this.playerService.getCompletedMatches;
    standings = this.playerService.getStandings;

    // Local navigation state
    activeSection = signal<'matches' | 'stats' | 'standings' | 'league-details'>('matches');
    selectedRound = signal<string>('');
    editingMatchId = signal<string | null>(null);
    scoreError = signal<string | null>(null);

    // Collapsible section state (all open by default)
    upcomingExpanded = signal(true);
    standingsExpanded = signal(true);
    completedExpanded = signal(true);

    // Viewed player (set when clicking a standings row)
    viewedPlayer = signal<{ name: string; email: string; rating: number } | null>(null);
    selectedPlayerMatches = signal<UpcomingMatch[]>([]);

    // The player's default round/group: earliest upcoming, or latest completed as fallback
    currentGroupRound = computed(() => {
        const upcoming = this.upcomingMatches();
        if (upcoming.length > 0) {
            const sorted = [...upcoming].sort((a, b) => (a.roundId || 0) - (b.roundId || 0));
            const m = sorted[0];
            if (m.roundId && m.groupId) {
                return { roundId: m.roundId, groupId: m.groupId, roundName: m.roundName || '' };
            }
        }
        const completed = this.completedMatches();
        if (completed.length > 0) {
            const sorted = [...completed].sort((a, b) => (b.roundId || 0) - (a.roundId || 0));
            const m = sorted[0];
            if (m.roundId && m.groupId) {
                return { roundId: m.roundId, groupId: m.groupId, roundName: m.roundName || '' };
            }
        }
        return null;
    });

    // All unique round/group combinations the player has matches in, sorted newest first
    availableGroupRounds = computed(() => {
        const allMatches = [...this.upcomingMatches(), ...this.completedMatches()];
        const seen = new Map<string, { roundId: number; groupId: number; roundName: string }>();
        allMatches.forEach(m => {
            if (m.roundId && m.groupId) {
                const key = `${m.roundId}-${m.groupId}`;
                if (!seen.has(key)) {
                    seen.set(key, { roundId: m.roundId, groupId: m.groupId, roundName: m.roundName || `Round ${m.roundId}` });
                }
            }
        });
        return Array.from(seen.values()).sort((a, b) => b.roundId - a.roundId || a.groupId - b.groupId);
    });

    // User-selected round/group key ("roundId-groupId"), null means use the default
    selectedGroupRoundKey = signal<string | null>(null);

    // The effective round/group for the standings display
    activeGroupRound = computed(() => {
        const key = this.selectedGroupRoundKey();
        if (key) {
            const found = this.availableGroupRounds().find(r => `${r.roundId}-${r.groupId}` === key);
            if (found) return found;
        }
        return this.currentGroupRound();
    });

    // Standings for the active group/round, sourced from raw league data (all players)
    currentGroupStandings = computed(() => {
        const cr = this.activeGroupRound();
        if (!cr) return [];
        return this.playerService.getGroupStandingsForRound(cr.groupId, cr.roundId);
    });

    filteredCompletedMatches = computed(() => {
        const round = this.selectedRound();
        const matches = this.completedMatches();
        if (!round) return matches;
        return matches.filter(m => String(m.roundId) === round);
    });

    viewedUpcomingMatches = computed(() => {
        const vp = this.viewedPlayer();
        if (!vp || vp.email === this.playerService.getCurrentPlayerId().toLowerCase()) {
            return this.upcomingMatches();
        }
        return this.selectedPlayerMatches().filter(m => m.status !== 'completed');
    });

    viewedCompletedMatches = computed(() => {
        const vp = this.viewedPlayer();
        if (!vp || vp.email === this.playerService.getCurrentPlayerId().toLowerCase()) {
            return this.filteredCompletedMatches();
        }
        let matches = this.selectedPlayerMatches().filter(m => m.status === 'completed');
        const round = this.selectedRound();
        if (round) matches = matches.filter(m => String(m.roundId) === round);
        return matches;
    });

    tempScore1 = signal<string>('');
    tempScore2 = signal<string>('');

    setActiveSection(section: 'matches' | 'stats' | 'standings' | 'league-details') {
        this.activeSection.set(section);
        if (section !== 'matches') {
            this.viewedPlayer.set(null);
            this.selectedPlayerMatches.set([]);
        }
    }

    setSelectedRound(roundId: string) {
        this.selectedRound.set(roundId);
    }

    // Get unique rounds from all matches
    getAvailableRounds(): { id: string; name: string }[] {
        const allMatches = [...this.upcomingMatches(), ...this.completedMatches()];
        const roundsMap = new Map<number, string>();

        allMatches.forEach(match => {
            if (match.roundId && !roundsMap.has(match.roundId)) {
                roundsMap.set(match.roundId, match.roundName || `Round ${match.roundId}`);
            }
        });

        return Array.from(roundsMap.entries()).map(([id, name]) => ({ id: String(id), name }));
    }

    // Get unique groups for the selected round
    getGroupsForRound(roundId: string): number[] {
        const allMatches = [...this.upcomingMatches(), ...this.completedMatches()];
        const groups = new Set<number>();
        const rId = Number(roundId);

        allMatches
            .filter(m => m.roundId === rId && m.groupId)
            .forEach(m => groups.add(m.groupId!));

        return Array.from(groups).sort((a, b) => a - b);
    }

    // Get standings for a specific group in a specific round
    getStandingsForGroupAndRound(groupId: string | number, roundId: string): any[] {
        const allMatches = [...this.upcomingMatches(), ...this.completedMatches()];
        const gId = Number(groupId);
        const rId = Number(roundId);

        // Get completed matches for this group and round
        const groupRoundMatches = allMatches.filter(m =>
            m.groupId === gId &&
            m.roundId === rId &&
            m.status === 'completed'
        );

        // Calculate standings from these matches
        const standingsMap = new Map<string, { email: string; name: string; totalScore: number; matchesPlayed: number }>();

        groupRoundMatches.forEach(match => {
            // Add players from my team
            match.myTeamPlayerIds.forEach(email => {
                const player = match.players.find(p => p.id === email);
                if (player) {
                    let entry = standingsMap.get(email);
                    if (!entry) {
                        entry = { email, name: player.name, totalScore: 0, matchesPlayed: 0 };
                        standingsMap.set(email, entry);
                    }
                    entry.totalScore += match.team1Score || 0;
                    entry.matchesPlayed += 1;
                }
            });

            // Add players from opponent team
            match.opponentTeamPlayerIds.forEach(email => {
                const player = match.players.find(p => p.id === email);
                if (player) {
                    let entry = standingsMap.get(email);
                    if (!entry) {
                        entry = { email, name: player.name, totalScore: 0, matchesPlayed: 0 };
                        standingsMap.set(email, entry);
                    }
                    entry.totalScore += match.team2Score || 0;
                    entry.matchesPlayed += 1;
                }
            });
        });

        return Array.from(standingsMap.values()).sort((a, b) => b.totalScore - a.totalScore);
    }

    selectLeague(leagueId: string) {
        this.playerService.selectLeague(leagueId);
    }

    setEditingMatch(id: string | null) {
        this.editingMatchId.set(id);
        this.scoreError.set(null);
        this.tempScore1.set('');
        this.tempScore2.set('');
    }

    submitScore(match: UpcomingMatch, s1?: string, s2?: string) {
        const val1 = s1 !== undefined ? s1 : this.tempScore1();
        const val2 = s2 !== undefined ? s2 : this.tempScore2();

        const score1 = parseInt(val1, 10);
        const score2 = parseInt(val2, 10);

        if (isNaN(score1) || isNaN(score2) || score1 < 0 || score2 < 0) {
            this.scoreError.set('Enter both scores as whole numbers (0 or more).');
            return;
        }
        if (score1 === score2) {
            this.scoreError.set('The two scores can’t be equal — a match needs a winner.');
            return;
        }
        this.scoreError.set(null);

        this.playerService.updateMatchScore(
            match.leagueId,
            match.id,
            score1,
            score2,
            match.myTeamName,
            match.opponentTeamName
        ).subscribe(success => {
            if (success) {
                this.editingMatchId.set(null);
                this.scoreError.set(null);
                this.tempScore1.set('');
                this.tempScore2.set('');
                this.toast.success('Score saved.');
            } else {
                this.scoreError.set("We couldn't save that score. Please try again.");
            }
        });
    }

    getPlayDays(): { day: number, date: Date, withdrawn: boolean, reason?: string }[] {
        const league = this.selectedLeague();
        if (!league || !league.startDate || !league.duration) return [];

        const durationInt = parseInt(league.duration, 10) || 0;
        const days = [];
        // Ensure we handle the date correctly
        const start = new Date(league.startDate);
        const myEmail = this.playerService.getCurrentPlayerId().toLowerCase();

        for (let i = 1; i <= durationInt; i++) {
            const playDate = new Date(start.getTime() + (i - 1) * 7 * 24 * 60 * 60 * 1000);
            const withdrawal = league.withdrawals?.find(w => w.play_day === i && w.email.toLowerCase() === myEmail);

            days.push({
                day: i,
                date: playDate,
                withdrawn: !!withdrawal,
                reason: withdrawal?.reason
            });
        }
        return days;
    }

    isFutureDate(date: Date): boolean {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const playDate = new Date(date);
        playDate.setHours(0, 0, 0, 0);
        return playDate > today;
    }

    withdrawFromDay(leagueId: string, playDay: number) {
        const reason = prompt(`Please enter a reason for withdrawing from Play Day ${playDay}:`);
        if (reason !== null && reason.trim() !== '') {
            this.playerService.withdrawFromPlayDay(leagueId, playDay, reason.trim()).subscribe(success => {
                if (success) {
                    this.toast.success(`You've been withdrawn from Play Day ${playDay}.`);
                } else {
                    this.toast.error("We couldn't process that withdrawal. Please try again.");
                }
            });
        }
    }

    viewPlayerMatches(entry: PlayerStanding): void {
        const allMatches = [...this.upcomingMatches(), ...this.completedMatches()];
        const playerInMatch = allMatches
            .flatMap(m => m.players)
            .find(p => p.id.toLowerCase() === entry.email.toLowerCase());
        const rating = playerInMatch?.rating ?? 0;

        this.viewedPlayer.set({ name: entry.name, email: entry.email.toLowerCase(), rating });
        this.selectedPlayerMatches.set(this.playerService.getMatchesForEmail(entry.email));
        this.setActiveSection('matches');
    }

    clearViewedPlayer(): void {
        this.viewedPlayer.set(null);
        this.selectedPlayerMatches.set([]);
    }

    getInitials(name: string): string {
        const parts = name.trim().split(/\s+/);
        return parts.length >= 2
            ? `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
            : name.slice(0, 2).toUpperCase();
    }

    viewMatchDetail(matchId: string) {
        this.router.navigate(['/player/match', matchId]);
    }

    formatDate(date: Date): string {
        const today = new Date();
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);

        const matchDate = new Date(date);

        if (matchDate.toDateString() === today.toDateString()) {
            return 'Today';
        } else if (matchDate.toDateString() === tomorrow.toDateString()) {
            return 'Tomorrow';
        } else {
            return matchDate.toLocaleDateString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric'
            });
        }
    }

    getTeammates(match: any): string {
        const myId = this.playerService.getCurrentPlayerId();
        return match.players
            .filter((p: any) => match.myTeamPlayerIds.includes(p.id) && p.id !== myId)
            .map((p: any) => p.name)
            .join(', ');
    }

    getOpponents(match: any): string {
        return match.players
            .filter((p: any) => match.opponentTeamPlayerIds.includes(p.id))
            .map((p: any) => p.name)
            .join(', ');
    }

}
