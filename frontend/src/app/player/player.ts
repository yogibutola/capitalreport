// Reusing interfaces from league.ts where possible or defining new ones specific to player view if needed
import { LeagueRoundPayload, RoundItem, GroupItem, MatchItem, TeamItem, TeamMember } from '../league/league';
import { Injectable, signal, computed, inject, effect } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AuthService } from '../auth/auth';
import { catchError, map } from 'rxjs/operators';
import { Observable, of } from 'rxjs';

export interface PlayerWithdrawal {
    league_id: string;
    email: string;
    play_day: number;
    reason: string;
}

export interface PlayerLeague {
    id: string;
    name: string;
    status: 'active' | 'upcoming' | 'completed';
    startDate: Date;
    endDate: Date;
    duration?: string;
    clubName?: string;
    location?: string;
    withdrawals?: PlayerWithdrawal[];
}

export interface MatchPlayer {
    id: string;
    name: string;
    rating: number;
}

export interface PlayerStanding {
    email: string;
    name: string;
    totalScore: number;
    matchesPlayed: number;
    wins: number;
    losses: number;
}

export interface UpcomingMatch {
    id: string;
    leagueId: string;
    leagueName: string;
    date: Date;
    time: string;
    court: string;
    status: 'upcoming' | 'in-progress' | 'completed';
    players: MatchPlayer[];
    myTeamPlayerIds: string[];
    opponentTeamPlayerIds: string[];
    // Additional fields from API
    roundId?: number;
    roundName?: string;
    groupId?: number;
    team1Score?: number;
    team2Score?: number;
    myTeamName?: string;
    opponentTeamName?: string;
}

@Injectable({
    providedIn: 'root'
})
export class PlayerService {
    // Mock current player ID
    private currentPlayerId = signal('1');

    // Mock leagues the player is part of
    private leagues = signal<PlayerLeague[]>([]);

    // All available leagues
    private allLeagues = signal<PlayerLeague[]>([]);

    // Selected league ID
    selectedLeagueId = signal<string | null>(null);


    // Mock upcoming matches
    private matches = signal<UpcomingMatch[]>([]);

    // League standings
    private standings = signal<PlayerStanding[]>([]);

    // Computed: Get all leagues player is in
    getLeagues = computed(() => this.leagues());

    // Computed: Get status of all available leagues
    getAllLeagues = computed(() => this.allLeagues());

    // Computed: Leagues the player has not joined, newest start date first
    getAvailableLeagues = computed(() => {
        const registeredIds = new Set(this.leagues().map(l => l.id));
        return this.allLeagues()
            .filter(l => !registeredIds.has(l.id))
            .sort((a, b) => new Date(b.startDate).getTime() - new Date(a.startDate).getTime());
    });

    // Computed: Get active leagues only
    getActiveLeagues = computed(() => {
        const leagues = this.leagues();
        console.log('getActiveLeagues computed triggered, leagues count:', leagues.length);
        return leagues.filter(l => l.status === 'active' || l.status === 'upcoming');
    });

    // Computed: Get matches filtered by selected league (Upcoming only)
    getUpcomingMatches = computed(() => {
        const selectedId = this.selectedLeagueId();
        const allMatches = this.matches();
        console.log(`getUpcomingMatches computed: selectedLeagueId=${selectedId}, TotalMatches=${allMatches.length}`);

        const matches = allMatches.filter(m => m.status !== 'completed');
        if (!selectedId) {
            return matches;
        }
        const filtered = matches.filter(m => String(m.leagueId) === String(selectedId));
        console.log(`getUpcomingMatches: returning ${filtered.length} matches`);
        return filtered;
    });

    // Computed: Get completed matches filtered by selected league
    getCompletedMatches = computed(() => {
        const selectedId = this.selectedLeagueId();
        const allMatches = this.matches();
        console.log(`getCompletedMatches computed: selectedLeagueId=${selectedId}, TotalMatches=${allMatches.length}`);

        const matches = allMatches.filter(m => m.status === 'completed');
        if (!selectedId) {
            return matches;
        }
        const filtered = matches.filter(m => String(m.leagueId) === String(selectedId));
        console.log(`getCompletedMatches: returning ${filtered.length} matches`);
        return filtered;
    });

    // Computed: Get league standings
    getStandings = computed(() => this.standings());

    // Computed: Get selected league
    getSelectedLeague = computed(() => {
        const selectedId = this.selectedLeagueId();
        if (!selectedId) return null;
        return this.leagues().find(l => l.id === selectedId);
    });

    // Raw league API response preserved so any player's matches can be parsed on demand
    private rawLeagueDetails: { details: any; leagueId: string; leagueName: string } | null = null;

    private http = inject(HttpClient);
    private authService = inject(AuthService);

    constructor() {
        // Automatically fetch leagues when current user changes
        effect(() => {
            const user = this.authService.currentUser();
            if (user?.email) {
                this.currentPlayerId.set(user.email);
                this.fetchLeaguesForPlayer(user.email);
            } else {
                this.leagues.set([]);
                this.currentPlayerId.set('1');
            }
        });
    }

    fetchLeaguesForPlayer(email: string) {
        const emailLower = email.toLowerCase();
        console.log(`[PlayerService] Fetching leagues for: ${emailLower}`);
        this.http.get<any>(`api/v1/player/league/${emailLower}`).pipe(
            map(data => {
                console.log('[PlayerService] Player leagues API response:', data);
                if (!data) return [];
                const leaguesList = Array.isArray(data) ? data : (data.leagues || (data.data ? data.data : []));

                return leaguesList.map((l: any) => ({
                    id: String(l.id || l._id || l.league_id || crypto.randomUUID()),
                    name: l.league_name || l.name || 'Unknown League',
                    status: (l.status || l.league_status || 'active').toLowerCase(),
                    startDate: new Date(l.startDate || l.league_start_date || new Date()),
                    endDate: new Date(l.endDate || l.league_end_date || new Date()),
                    clubName: l.club_name || l.clubName,
                    location: l.location
                }));
            }),
            catchError(err => {
                console.error('[PlayerService] Error fetching player leagues:', err);
                return of([]);
            })
        ).subscribe((leagues: PlayerLeague[]) => {
            console.log('[PlayerService] Processed player leagues:', leagues);
            this.leagues.set(leagues);
            if (leagues.length > 0) {
                const currentSelectedId = this.selectedLeagueId();
                const stillExists = leagues.find(l => l.id === currentSelectedId);

                if (!currentSelectedId || !stillExists) {
                    console.log('[PlayerService] Syncing selectedLeagueId to:', leagues[0].id);
                    this.selectedLeagueId.set(leagues[0].id);
                }

                const leagueToFetch = leagues.find(l => l.id === this.selectedLeagueId()) || leagues[0];
                this.fetchLeagueDetailsByName(leagueToFetch.name, leagueToFetch.id);
            } else {
                this.selectedLeagueId.set(null);
                this.matches.set([]);
            }
        });
    }

    fetchLeagueDetailsByName(leagueName: string, leagueId: string) {
        console.log(`[PlayerService] Fetching details for league: ${leagueName} (ID: ${leagueId})`);

        // Try fetching by name
        const encodedName = encodeURIComponent(leagueName);
        this.http.get<any>(`api/v1/league/name/${encodedName}`).pipe(
            catchError(err => {
                console.error(`[PlayerService] Error fetching league details by name (${leagueName}):`, err);
                return of(null);
            })
        ).subscribe(details => {
            if (details) {
                this.leagues.update(leagues => leagues.map(l => {
                    if (l.id === leagueId) {
                        return {
                            ...l,
                            duration: details.league_duration,
                            withdrawals: details.withdrawals || []
                        };
                    }
                    return l;
                }));
            }

            const matches = this.parseLeagueDetails(details, leagueId, leagueName);

            // If no matches found by name, try fetching by ID (which daily-slotting uses via the name endpoint)
            if (matches.length === 0 && leagueId && String(leagueId) !== String(leagueName)) {
                console.log(`[PlayerService] No matches found by name, trying fetch by ID: ${leagueId}`);
                this.http.get<any>(`api/v1/league/name/${leagueId}`).pipe(
                    catchError(err => {
                        console.error(`[PlayerService] Error fetching league details by ID (${leagueId}):`, err);
                        return of(null);
                    })
                ).subscribe(idDetails => {
                    if (idDetails) {
                        this.leagues.update(leagues => leagues.map(l => {
                            if (l.id === leagueId) {
                                return {
                                    ...l,
                                    duration: idDetails.league_duration,
                                    withdrawals: idDetails.withdrawals || []
                                };
                            }
                            return l;
                        }));
                    }
                    const idMatches = this.parseLeagueDetails(idDetails, leagueId, leagueName);
                    this.matches.set(idMatches);
                });
            } else {
                this.matches.set(matches);
            }
        });
    }

    private parseLeagueDetails(details: any, leagueId: string, leagueName: string): UpcomingMatch[] {
        if (!details) {
            console.warn(`[PlayerService] No details returned for ${leagueName}.`);
            return [];
        }

        // Preserve raw data so getMatchesForEmail() can parse any player's view on demand
        this.rawLeagueDetails = { details, leagueId, leagueName };

        const userEmail = this.authService.currentUser()?.email;
        if (!userEmail) {
            console.warn('[PlayerService] No user email found, cannot filter matches.');
            return [];
        }

        const emailLower = userEmail.toLowerCase();
        const newMatches: UpcomingMatch[] = [];

        console.log(`[PlayerService] Processing details for ${leagueName}. Response has matches: ${!!details.matches}, rounds: ${!!details.rounds}`);

        const playersLookup = new Map<string, any>();
        if (details.players) {
            details.players.forEach((p: any) => {
                if (p.email) playersLookup.set(p.email.toLowerCase(), p);
            });
        }

        // --- Standings Calculation ---
        const standingsMap = new Map<string, PlayerStanding>();

        // Helper to add player score to standings
        const updateStanding = (player: any, score: number, isCompleted: boolean, isWin: boolean) => {
            if (!player || !player.email) return;
            const email = player.email.toLowerCase();
            let state = standingsMap.get(email);
            if (!state) {
                state = { email, name: player.name, totalScore: 0, matchesPlayed: 0, wins: 0, losses: 0 };
                standingsMap.set(email, state);
            }
            state.totalScore += score;
            if (isCompleted) {
                state.matchesPlayed += 1;
                if (isWin) { state.wins += 1; } else { state.losses += 1; }
            }
        };

        const processMatch = (m: any) => {
            // Support multiple team naming conventions
            const t1 = m.team_one || m.team1;
            const t2 = m.team_two || m.team2;

            if (!t1 || !t2) {
                console.warn(`[PlayerService] Skipping match ${m._id || m.match_id} due to missing team data.`, m);
                return;
            }

            // Support multiple player naming conventions
            const p1Raw = t1.player_one || t1.player1;
            const p2Raw = t1.player_two || t1.player2;
            const p3Raw = t2.player_one || t2.player1;
            const p4Raw = t2.player_two || t2.player2;

            // Helper to normalize player data (could be string email or object)
            const normalizePlayer = (p: any) => {
                if (!p) return null;
                if (typeof p === 'string') {
                    const lookup = playersLookup.get(p.toLowerCase());
                    return {
                        email: p.toLowerCase(),
                        firstName: lookup?.firstName || '',
                        lastName: lookup?.lastName || '',
                        name: lookup ? `${lookup.firstName} ${lookup.lastName}` : p,
                        dupr_rating: lookup?.dupr_rating || 0
                    };
                }
                const email = (p.email || p.id || '').toLowerCase();
                const lookup = playersLookup.get(email);
                return {
                    email: email,
                    firstName: p.firstName || lookup?.firstName || '',
                    lastName: p.lastName || lookup?.lastName || '',
                    name: p.name || (p.firstName ? `${p.firstName} ${p.lastName}` : (lookup ? `${lookup.firstName} ${lookup.lastName}` : 'Unknown')),
                    dupr_rating: p.dupr_rating || lookup?.dupr_rating || 0
                };
            };

            const p1 = normalizePlayer(p1Raw);
            const p2 = normalizePlayer(p2Raw);
            const p3 = normalizePlayer(p3Raw);
            const p4 = normalizePlayer(p4Raw);

            const allPlayers = [p1, p2, p3, p4].filter(p => !!p);

            const isCompleted = (String(m.match_status)?.toLowerCase() === 'completed' || String(m.match_status)?.toLowerCase() === 'finished' || (Number(t1.score || 0) > 0 || Number(t2.score || 0) > 0));

            // Update standings for EVERYONE in the match
            if (isCompleted) {
                const s1 = Number(t1.score || 0);
                const s2 = Number(t2.score || 0);
                const team1Won = s1 > s2;
                [p1, p2].forEach(p => updateStanding(p, s1, true, team1Won));
                [p3, p4].forEach(p => updateStanding(p, s2, true, !team1Won));
            }

            // Check if current user is in this match for the dashboard lists
            const isParticipant = allPlayers.some(p => p?.email === emailLower);

            if (isParticipant) {
                const myTeamEmails = [p1, p2].filter(p => !!p).map(p => p!.email);
                const isTeam1 = myTeamEmails.includes(emailLower);

                console.log(`[PlayerService] Match ${m._id || m.match_id}: USER FOUND in ${isTeam1 ? 'Team 1' : 'Team 2'}`);

                // Date/Time parsing
                let matchDate = m.date ? new Date(m.date) : new Date();
                let timeStr = String(m.time || 'TBD');
                if (timeStr.includes('T')) {
                    const parts = timeStr.split('T');
                    if (isNaN(matchDate.getTime())) matchDate = new Date(parts[0]);
                    timeStr = parts[1].substring(0, 5);
                } else if (timeStr.includes('-') || timeStr.includes('/')) {
                    const tempDate = new Date(timeStr);
                    if (!isNaN(tempDate.getTime())) {
                        matchDate = tempDate;
                        timeStr = tempDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
                    }
                }

                newMatches.push({
                    id: String(m._id || m.match_id),
                    leagueId: String(leagueId || m.league_id || details.league_id),
                    leagueName: m.league_name || details.league_name || leagueName,
                    date: isNaN(matchDate.getTime()) ? new Date() : matchDate,
                    time: timeStr,
                    court: String(m.court_number || m.court || 'TBD'),
                    players: allPlayers.map(p => ({
                        id: p!.email,
                        name: p!.name,
                        rating: p!.dupr_rating
                    })),
                    myTeamPlayerIds: isTeam1
                        ? [p1?.email, p2?.email].filter((e): e is string => !!e)
                        : [p3?.email, p4?.email].filter((e): e is string => !!e),
                    opponentTeamPlayerIds: isTeam1
                        ? [p3?.email, p4?.email].filter((e): e is string => !!e)
                        : [p1?.email, p2?.email].filter((e): e is string => !!e),
                    roundId: Number(m.round_id || 0),
                    roundName: m.round_name || m.roundName || '',
                    groupId: Number(m.group_id || 0),
                    status: isCompleted ? 'completed' : 'upcoming',
                    team1Score: isTeam1 ? Number(t1.score || 0) : Number(t2.score || 0),
                    team2Score: isTeam1 ? Number(t2.score || 0) : Number(t1.score || 0),
                    myTeamName: isTeam1 ? t1.team_name : t2.team_name,
                    opponentTeamName: isTeam1 ? t2.team_name : t1.team_name
                });
            } else {
                // Log why it failed to help debugging
                const matchEmails = allPlayers.map(p => p?.email);
                console.debug(`[PlayerService] Match ${m._id || m.match_id}: User ${emailLower} NOT found in [${matchEmails.join(', ')}]`);
            }
        };

        if (details.matches && Array.isArray(details.matches)) {
            console.log(`[PlayerService] Processing ${details.matches.length} top-level matches.`);
            details.matches.forEach((m: any) => processMatch(m));
        }

        // Only check rounds if no matches found in top-level list
        if (newMatches.length === 0 && details.rounds && Array.isArray(details.rounds)) {
            console.log(`[PlayerService] Processing ${details.rounds.length} rounds.`);
            details.rounds.forEach((round: any) => {
                round.group?.forEach((group: any) => {
                    group.match?.forEach((match: any) => processMatch(match));
                });
            });
        }

        // Set standings sorted by total score
        const sortedStandings = Array.from(standingsMap.values())
            .sort((a, b) => b.totalScore - a.totalScore);
        this.standings.set(sortedStandings);
        console.log(`[PlayerService] Standings calculated for ${sortedStandings.length} players.`);

        console.log(`[PlayerService] Successfully mapped ${newMatches.length} matches for user.`);
        return newMatches;
    }


    // Get match by ID
    getMatchById(matchId: string): UpcomingMatch | undefined {
        return this.matches().find((m: UpcomingMatch) => String(m.id) === String(matchId));
    }

    // Select a league
    selectLeague(leagueId: string) {
        this.selectedLeagueId.set(leagueId);
        const league = this.leagues().find((l: PlayerLeague) => l.id === leagueId);
        if (league) {
            this.fetchLeagueDetailsByName(league.name, league.id);
        }
    }

    // Get current player ID
    getCurrentPlayerId() {
        return this.currentPlayerId();
    }

    updateMatchScore(leagueId: string, matchId: string, score1: number, score2: number, teamName1?: string, teamName2?: string) {
        console.log(`Sending score update for ${matchId} in league ${leagueId}: ${teamName1 || 'Team 1'} (${score1}) - ${teamName2 || 'Team 2'} (${score2})`);

        const payload = {
            league_id: leagueId,
            match_id: matchId,
            score_team_1: score1,
            score_team_2: score2,
            team_1_name: teamName1,
            team_2_name: teamName2,
            match_status: 'completed'
        };

        return this.http.post('api/v1/league/match/score', payload).pipe(
            map(res => {
                console.log('Score update response:', res);
                // Update local signal to reflect changes immediately
                this.matches.update(currentMatches =>
                    currentMatches.map(m =>
                        m.id === matchId
                            ? { ...m, status: 'completed' as const, team1Score: score1, team2Score: score2 }
                            : m
                    )
                );
                return true;
            }),
            catchError(err => {
                console.error('Error updating score:', err);
                return of(false);
            })
        );
    }

    fetchAllLeagues() {
        this.http.get<any[]>('api/v1/all_leagues').pipe(
            map(data => {
                if (!Array.isArray(data)) return [];
                return data.map((l: any) => ({
                    id: String(l.id || l._id || l.league_id || crypto.randomUUID()),
                    name: l.league_name || l.name || 'Unknown League',
                    status: (l.status || l.league_status || 'active').toLowerCase(),
                    startDate: new Date(l.startDate || l.league_start_date || new Date()),
                    endDate: new Date(l.endDate || l.league_end_date || new Date()),
                    duration: l.duration || l.league_duration || undefined,
                    clubName: l.club_name || l.clubName,
                    location: l.location
                }));
            }),
            catchError(err => {
                console.error('Error fetching all leagues:', err);
                return of([]);
            })
        ).subscribe(leagues => {
            this.allLeagues.set(leagues);
        });
    }

    registerForLeague(leagueId: string): Observable<boolean> {
        const user = this.authService.currentUser();
        if (!user) return of(false);

        const payload = {
            league_id: leagueId,
            email: user.email
        };

        return this.http.post('api/v1/league/register', payload).pipe(
            map(res => {
                console.log('Registration successful:', res);
                this.fetchLeaguesForPlayer(user.email);
                return true;
            }),
            catchError(err => {
                console.log('Registration failed: ' + err.message);
                console.error('Registration error:', err);
                return of(false);
            })
        );
    }

    unregisterFromLeague(leagueId: string): Observable<void> {
        return this.http.delete<void>(`api/v1/league/${leagueId}/player`).pipe(
            map(() => {
                this.leagues.update(ls => ls.filter(l => l.id !== leagueId));
                const remaining = this.leagues();
                if (this.selectedLeagueId() === leagueId) {
                    this.selectedLeagueId.set(remaining.length > 0 ? remaining[0].id : null);
                }
            })
        );
    }

    /** Returns all matches in the current league where `email` is a participant, from their perspective. */
    getMatchesForEmail(email: string): UpcomingMatch[] {
        if (!this.rawLeagueDetails) return [];
        const { details, leagueId, leagueName } = this.rawLeagueDetails;
        return this.parseMatchesForEmail(details, leagueId, leagueName, email.toLowerCase());
    }

    private parseMatchesForEmail(details: any, leagueId: string, leagueName: string, emailLower: string): UpcomingMatch[] {
        const playersLookup = new Map<string, any>();
        if (details.players) {
            details.players.forEach((p: any) => {
                if (p.email) playersLookup.set(p.email.toLowerCase(), p);
            });
        }

        const normalizePlayer = (p: any) => {
            if (!p) return null;
            if (typeof p === 'string') {
                const lk = playersLookup.get(p.toLowerCase());
                return { email: p.toLowerCase(), name: lk ? `${lk.firstName} ${lk.lastName}` : p, dupr_rating: lk?.dupr_rating || 0 };
            }
            const email = (p.email || p.id || '').toLowerCase();
            const lk = playersLookup.get(email);
            return {
                email,
                name: p.name || (p.firstName ? `${p.firstName} ${p.lastName}` : (lk ? `${lk.firstName} ${lk.lastName}` : 'Unknown')),
                dupr_rating: p.dupr_rating || lk?.dupr_rating || 0
            };
        };

        const results: UpcomingMatch[] = [];

        const processMatch = (m: any) => {
            const t1 = m.team_one || m.team1;
            const t2 = m.team_two || m.team2;
            if (!t1 || !t2) return;

            const p1 = normalizePlayer(t1.player_one || t1.player1);
            const p2 = normalizePlayer(t1.player_two || t1.player2);
            const p3 = normalizePlayer(t2.player_one || t2.player1);
            const p4 = normalizePlayer(t2.player_two || t2.player2);

            const allPlayers = [p1, p2, p3, p4].filter(Boolean);
            if (!allPlayers.some(p => p!.email === emailLower)) return;

            const s1 = Number(t1.score || 0);
            const s2 = Number(t2.score || 0);
            const isCompleted = (
                String(m.match_status)?.toLowerCase() === 'completed' ||
                String(m.match_status)?.toLowerCase() === 'finished' ||
                s1 > 0 || s2 > 0
            );

            const isTeam1 = [p1, p2].some(p => p?.email === emailLower);

            let matchDate = m.date ? new Date(m.date) : new Date();
            let timeStr = String(m.time || 'TBD');
            if (timeStr.includes('T')) {
                const parts = timeStr.split('T');
                if (isNaN(matchDate.getTime())) matchDate = new Date(parts[0]);
                timeStr = parts[1].substring(0, 5);
            }

            results.push({
                id: String(m._id || m.match_id),
                leagueId: String(leagueId),
                leagueName: m.league_name || details.league_name || leagueName,
                date: isNaN(matchDate.getTime()) ? new Date() : matchDate,
                time: timeStr,
                court: String(m.court_number || m.court || 'TBD'),
                players: allPlayers.map(p => ({ id: p!.email, name: p!.name, rating: p!.dupr_rating })),
                myTeamPlayerIds: isTeam1
                    ? [p1?.email, p2?.email].filter((e): e is string => !!e)
                    : [p3?.email, p4?.email].filter((e): e is string => !!e),
                opponentTeamPlayerIds: isTeam1
                    ? [p3?.email, p4?.email].filter((e): e is string => !!e)
                    : [p1?.email, p2?.email].filter((e): e is string => !!e),
                roundId: Number(m.round_id || 0),
                roundName: m.round_name || m.roundName || '',
                groupId: Number(m.group_id || 0),
                status: isCompleted ? 'completed' : 'upcoming',
                team1Score: isTeam1 ? s1 : s2,
                team2Score: isTeam1 ? s2 : s1,
                myTeamName: isTeam1 ? t1.team_name : t2.team_name,
                opponentTeamName: isTeam1 ? t2.team_name : t1.team_name
            });
        };

        if (details.matches && Array.isArray(details.matches)) {
            details.matches.forEach((m: any) => processMatch(m));
        }
        if (results.length === 0 && details.rounds && Array.isArray(details.rounds)) {
            details.rounds.forEach((round: any) => {
                round.group?.forEach((group: any) => {
                    group.match?.forEach((match: any) => processMatch(match));
                });
            });
        }

        return results;
    }

    /** Returns standings for all players in a specific group and round, computed from raw league data. */
    getGroupStandingsForRound(groupId: number, roundId: number): PlayerStanding[] {
        if (!this.rawLeagueDetails) return [];
        const { details } = this.rawLeagueDetails;

        const playersLookup = new Map<string, any>();
        if (details.players) {
            details.players.forEach((p: any) => {
                if (p.email) playersLookup.set(p.email.toLowerCase(), p);
            });
        }

        const normalizePlayer = (p: any) => {
            if (!p) return null;
            if (typeof p === 'string') {
                const lk = playersLookup.get(p.toLowerCase());
                return { email: p.toLowerCase(), name: lk ? `${lk.firstName} ${lk.lastName}` : p };
            }
            const email = (p.email || p.id || '').toLowerCase();
            const lk = playersLookup.get(email);
            return {
                email,
                name: p.name || (p.firstName ? `${p.firstName} ${p.lastName}` : (lk ? `${lk.firstName} ${lk.lastName}` : 'Unknown'))
            };
        };

        const standingsMap = new Map<string, PlayerStanding>();
        const processedMatchIds = new Set<string>();
        let completedMatchCount = 0;

        const processMatch = (m: any) => {
            if (Number(m.group_id) !== groupId || Number(m.round_id) !== roundId) return;

            // Deduplicate: skip if this match_id was already processed from another source
            const matchId = String(m.match_id || m._id || '');
            if (matchId && processedMatchIds.has(matchId)) return;
            if (matchId) processedMatchIds.add(matchId);

            const t1 = m.team_one || m.team1;
            const t2 = m.team_two || m.team2;
            if (!t1 || !t2) return;

            const s1 = Number(t1.score || 0);
            const s2 = Number(t2.score || 0);
            const isCompleted = (
                String(m.match_status)?.toLowerCase() === 'completed' ||
                String(m.match_status)?.toLowerCase() === 'finished' ||
                s1 > 0 || s2 > 0
            );
            if (!isCompleted) return;

            completedMatchCount++;
            const team1Won = s1 > s2;
            const players1 = [normalizePlayer(t1.player_one || t1.player1), normalizePlayer(t1.player_two || t1.player2)];
            const players2 = [normalizePlayer(t2.player_one || t2.player1), normalizePlayer(t2.player_two || t2.player2)];

            const updateEntry = (player: any, score: number, isWin: boolean) => {
                if (!player?.email) return;
                const email = player.email.toLowerCase();
                let entry = standingsMap.get(email);
                if (!entry) {
                    entry = { email, name: player.name, totalScore: 0, matchesPlayed: 0, wins: 0, losses: 0 };
                    standingsMap.set(email, entry);
                }
                entry.totalScore += score;
                entry.matchesPlayed += 1;
                if (isWin) entry.wins += 1; else entry.losses += 1;
            };

            players1.forEach(p => updateEntry(p, s1, team1Won));
            players2.forEach(p => updateEntry(p, s2, !team1Won));
        };

        if (details.matches && Array.isArray(details.matches)) {
            details.matches.forEach((m: any) => processMatch(m));
        }
        // Only fall back to embedded round matches if no completed matches were found in
        // details.matches — mirrors the same guard used in parseLeagueDetails /
        // parseMatchesForEmail, and prevents double-counting when both sources are populated.
        if (completedMatchCount === 0 && details.rounds && Array.isArray(details.rounds)) {
            details.rounds.forEach((round: any) => {
                round.group?.forEach((group: any) => {
                    group.match?.forEach((match: any) => processMatch(match));
                });
            });
        }

        return Array.from(standingsMap.values()).sort((a, b) => b.totalScore - a.totalScore);
    }

    withdrawFromPlayDay(leagueId: string, playDay: number, reason: string): Observable<boolean> {
        const payload = {
            league_id: leagueId,
            play_day: playDay,
            reason: reason
        };

        return this.http.post('api/v1/league/withdraw', payload).pipe(
            map(res => {
                console.log('Withdrawal successful:', res);
                const user = this.authService.currentUser();
                // Refresh the league details
                const league = this.leagues().find(l => l.id === leagueId);
                if (league) {
                    this.fetchLeagueDetailsByName(league.name, leagueId);
                }
                return true;
            }),
            catchError(err => {
                console.error('Withdrawal failed:', err);
                return of(false);
            })
        );
    }
}
