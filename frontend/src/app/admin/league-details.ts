import { Component, signal, computed, inject, effect } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { LeagueDetailsPayload, LeagueRoundPayload, LeagueService, Player, RoundItem } from '../league/league';

interface LeagueDetails {
    league_id: string;
    league_name: string;
    league_status: 'active' | 'pending';
    league_start_date: string;
    league_end_date: string;
    league_duration: string;
    players: Player[];
    rounds?: RoundItem[];
}

@Component({
    selector: 'app-league-details',
    standalone: true,
    imports: [CommonModule, RouterLink],
    templateUrl: './league-details.html',
    styleUrl: './league-details.css'
})
export class LeagueDetailsComponent {
    private route = inject(ActivatedRoute);
    private http = inject(HttpClient);
    private leagueService = inject(LeagueService);

    leagueId = signal<string | null>(null);
    leagueName = signal<string | null>(null);
    leagueDetails = signal<LeagueDetails | null>(null);
    loading = signal<boolean>(true);
    error = signal<string | null>(null);

    // Sorting state
    sortColumn = signal<'firstName' | 'lastName' | 'dupr_rating' | null>(null);
    sortDirection = signal<'asc' | 'desc'>('asc');

    // Computed sorted players list
    sortedPlayers = computed(() => {
        const details = this.leagueDetails();
        if (!details || !details.players) return [];

        const players = [...details.players];
        const column = this.sortColumn();
        const direction = this.sortDirection();

        if (!column) return players;

        players.sort((a, b) => {
            let valueA: string | number = a[column];
            let valueB: string | number = b[column];

            // Handle string comparison for names
            if (typeof valueA === 'string' && typeof valueB === 'string') {
                valueA = valueA.toLowerCase();
                valueB = valueB.toLowerCase();
            }

            if (valueA < valueB) return direction === 'asc' ? -1 : 1;
            if (valueA > valueB) return direction === 'asc' ? 1 : -1;
            return 0;
        });

        return players;
    });

    isRound1Slotted = computed(() => {
        const details = this.leagueDetails();
        if (!details || !details.rounds) return false;
        return details.rounds.some(r => r.round_id === 1);
    });

    constructor() {
        // Get league ID from route params
        this.route.params.subscribe(params => {
            const id = params['league_id'];
            this.leagueId.set(id);
        });

        // Fetch league details when league ID is available
        effect(() => {
            const id = this.leagueId();
            if (id) {
                this.fetchLeagueDetails(id);
            }
        }, { allowSignalWrites: true });
    }

    private fetchLeagueDetails(leagueId: string) {
        this.loading.set(true);
        this.error.set(null);

        // First, we need to get the league name from the ID
        // Since we're getting league_id from the route, we need to map it to league_name
        // We'll use the league_id as the league_name for the API call
        // This assumes the league_id in the route is actually the league_name

        console.log("Leage ID: " + leagueId);
        this.http.get<LeagueDetailsPayload>(`/api/v1/league/name/${leagueId}`).subscribe({
            next: (data) => {
                // Transform the response to LeagueDetails format
                const details: LeagueDetails = {
                    league_id: data.league_id as string,
                    league_name: data.league_name,
                    league_status: data.league_status,
                    league_start_date: data.league_start_date,
                    league_end_date: data.league_end_date,
                    league_duration: data.league_duration,
                    players: data.players,
                    rounds: data.rounds
                };

                // Populate LeagueService with players for slotting
                this.leagueService.setPlayers(data.players);

                this.leagueDetails.set(details);
                this.leagueName.set(data.league_name);
                this.loading.set(false);
            },
            error: (err) => {
                console.error('Error fetching league details:', err);
                this.error.set('Failed to load league details');
                this.loading.set(false);
            }
        });
    }

    private extractPlayersFromRounds(data: LeagueRoundPayload): Array<{
        firstName: string;
        lastName: string;
        email: string;
        dupr_rating: number;
    }> {
        const playersMap = new Map<string, {
            firstName: string;
            lastName: string;
            email: string;
            dupr_rating: number;
        }>();

        // Extract unique players from all rounds, groups, and matches
        if (data.rounds) {
            data.rounds.forEach(round => {
                if (round.group) {
                    round.group.forEach(group => {
                        if (group.match) {
                            group.match.forEach(match => {
                                // Add players from team_one
                                if (match.team_one) {
                                    [match.team_one.player_one, match.team_one.player_two].forEach(player => {
                                        if (player && player.email && !playersMap.has(player.email)) {
                                            playersMap.set(player.email, {
                                                firstName: player.firstName,
                                                lastName: player.lastName,
                                                email: player.email,
                                                dupr_rating: player.dupr_rating || 0
                                            });
                                        }
                                    });
                                }

                                // Add players from team_two
                                if (match.team_two) {
                                    [match.team_two.player_one, match.team_two.player_two].forEach(player => {
                                        if (player && player.email && !playersMap.has(player.email)) {
                                            playersMap.set(player.email, {
                                                firstName: player.firstName,
                                                lastName: player.lastName,
                                                email: player.email,
                                                dupr_rating: player.dupr_rating || 0
                                            });
                                        }
                                    });
                                }

                                // Add sitting player if exists
                                if (match.siting_player && match.siting_player.email && !playersMap.has(match.siting_player.email)) {
                                    playersMap.set(match.siting_player.email, {
                                        firstName: match.siting_player.firstName,
                                        lastName: match.siting_player.lastName,
                                        email: match.siting_player.email,
                                        dupr_rating: match.siting_player.dupr_rating || 0
                                    });
                                }
                            });
                        }
                    });
                }
            });
        }

        return Array.from(playersMap.values());
    }

    private extractPlayersFromLeagueDetails(data: LeagueDetailsPayload): Array<{
        firstName: string;
        lastName: string;
        email: string;
        dupr_rating: number;
    }> {
        const playersMap = new Map<string, {
            firstName: string;
            lastName: string;
            email: string;
            dupr_rating: number;
        }>();

        // Extract unique players from all rounds, groups, and matches
        if (data.players) {
            data.players.forEach(player => {
                if (player.email && !playersMap.has(player.email)) {
                    playersMap.set(player.email, {
                        firstName: player.firstName,
                        lastName: player.lastName,
                        email: player.email,
                        dupr_rating: player.dupr_rating || 0
                    });
                }
            });
        }

        return Array.from(playersMap.values());
    }


    getSlottingRoute(): string {
        const id = this.leagueId();
        return id ? `/league/slotting?league_id=${id}` : '/league/slotting';
    }

    sortBy(column: 'firstName' | 'lastName' | 'dupr_rating') {
        const currentColumn = this.sortColumn();

        if (currentColumn === column) {
            // Toggle direction if same column
            this.sortDirection.set(this.sortDirection() === 'asc' ? 'desc' : 'asc');
        } else {
            // Set new column and default to ascending
            this.sortColumn.set(column);
            this.sortDirection.set('asc');
        }
    }

    getSortIcon(column: 'firstName' | 'lastName' | 'dupr_rating'): string {
        if (this.sortColumn() !== column) return '⇅';
        return this.sortDirection() === 'asc' ? '↑' : '↓';
    }
}

