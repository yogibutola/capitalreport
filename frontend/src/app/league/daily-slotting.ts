import { Component, computed, signal, inject, effect, Injector } from '@angular/core';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { LeagueService, Player, LeagueRoundPayload, RoundItem, GroupItem, MatchItem, TeamItem, TeamMember, LeagueDetailsPayload } from './league';
import { AdminService } from '../admin/admin';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';

interface MatchSlot {
  id: string;
  team1: Player[];
  team2: Player[];
  score1?: number;
  score2?: number;
  time?: string;
  courtNumber?: string;
}

@Component({
  selector: 'app-daily-slotting',
  standalone: true,
  imports: [RouterLink, FormsModule, CommonModule],
  templateUrl: './daily-slotting.html',
  styleUrl: './daily-slotting.css'
})
export class DailySlottingComponent {
  private leagueService = inject(LeagueService);
  private adminService = inject(AdminService);
  private route = inject(ActivatedRoute);
  private http = inject(HttpClient);

  leagueId = signal<string | null>(null);
  league = computed(() => {
    const id = this.leagueId();
    if (!id) return undefined;
    const leagues = this.adminService.leagues();
    return leagues.find(l => l.league_id === id || l.league_name === id);
  });

  slottingDate = signal<string>(new Date().toISOString().split('T')[0]);
  collapsedGroups = signal<Set<string>>(new Set());

  // Support multiple rounds
  roundsData = signal<{ roundId: number, matches: Map<number, MatchSlot[]>, sitting: Map<number, Player[][]> }[]>([]);

  // State to track base players and withdrawals for filtering
  allLeaguePlayers = signal<Player[]>([]);
  leagueWithdrawals = signal<{ email: string; play_day: number; reason: string }[]>([]);
  leagueStartDate = signal<string>('');
  filteredPlayers = signal<Player[]>([]);

  playDay = computed(() => {
    const startDateStr = this.leagueStartDate();
    if (!startDateStr) return 1;
    const startDate = new Date(startDateStr);
    const targetDate = new Date(this.slottingDate());
    startDate.setHours(0, 0, 0, 0);
    targetDate.setHours(0, 0, 0, 0);
    const diffDays = Math.round((targetDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));
    return Math.max(1, Math.floor(diffDays / 7) + 1);
  });

  firstRoundOfDay = computed(() => (this.playDay() - 1) * 2 + 1);

  groups = computed(() => this.leagueService.getGroupsForPlayers(this.filteredPlayers()));

  nextRoundId = computed(() => {
    const rounds = this.roundsData();
    if (rounds.length === 0) return 1;
    return Math.max(...rounds.map(r => r.roundId)) + 1;
  });

  canSlotNextRound = computed(() => {
    const nextId = this.nextRoundId();
    if (nextId % 2 === 1) {
      // Odd round = first round of a day; just need players loaded
      return this.groups().length > 0;
    } else {
      // Even round = second round of a day; need the first round of this day to be fully scored
      const prevRound = this.roundsData().find(r => r.roundId === nextId - 1);
      if (!prevRound) return false;
      for (const [, matches] of prevRound.matches) {
        for (const m of matches) {
          if (m.score1 === undefined || m.score2 === undefined) return false;
        }
      }
      return true;
    }
  });
  constructor() {
    this.route.queryParams.subscribe(params => {
      const id = params['league_id'];
      this.leagueId.set(id);
      if (id) {
        this.fetchExistingSlotting(id);
      }
    });

    // Rounds are explicitly generated via user action
  }

  onDateChange() {
    this.filterAndSetPlayers();
  }

  private filterAndSetPlayers() {
    const players = this.allLeaguePlayers();
    const withdrawals = this.leagueWithdrawals();
    const startDateStr = this.leagueStartDate();

    if (!players.length) return;

    if (!startDateStr || !withdrawals.length) {
      this.filteredPlayers.set(players);
      return;
    }

    const day = this.playDay();
    const withdrawnEmails = new Set(
      withdrawals
        .filter(w => Number(w.play_day) === Number(day))
        .map(w => (w.email || '').toLowerCase())
    );

    console.log('--- SLOTTING FILTER ---');
    console.log('Calculated playDay:', day);
    console.log('Total withdrawals fetched:', withdrawals.length);

    const activePlayers = players.filter(p => !withdrawnEmails.has(p.email.toLowerCase()));
    this.filteredPlayers.set(activePlayers);
  }

  slotNextRound() {
    const nextId = this.nextRoundId();
    if (nextId % 2 === 1) {
      this.generateFirstRoundOfDay(nextId);
    } else {
      this.generateSecondRoundOfDay(nextId - 1);
    }
    this.saveRoundById(nextId);
  }

  generateFirstRoundOfDay(overrideRoundId?: number) {
    const roundId = overrideRoundId ?? this.firstRoundOfDay();
    // Derive play day from the round being slotted (not from the date picker) so
    // withdrawals are filtered for the correct day regardless of what date is selected.
    const roundPlayDay = Math.ceil(roundId / 2);
    const withdrawals = this.leagueWithdrawals();
    const withdrawnEmails = new Set(
      withdrawals
        .filter(w => Number(w.play_day) === roundPlayDay)
        .map(w => (w.email || '').toLowerCase())
    );
    const playersForDay = this.allLeaguePlayers().filter(
      p => !withdrawnEmails.has(p.email.toLowerCase())
    );
    const groups = this.leagueService.getGroupsForPlayers(playersForDay);
    const matchesMap = new Map<number, MatchSlot[]>();
    const sittingMap = new Map<number, Player[][]>();

    groups.forEach(group => {
      if (group.players.length === 5) {
        const sorted = [...group.players].sort((a, b) => b.dupr_rating - a.dupr_rating);
        const p = sorted;

        const matches: MatchSlot[] = [
          { id: `g${group.level}-r${roundId}-m1`, team1: [p[0], p[3]], team2: [p[1], p[2]], time: '09:00', courtNumber: '1' },
          { id: `g${group.level}-r${roundId}-m2`, team1: [p[0], p[1]], team2: [p[2], p[4]], time: '09:20', courtNumber: '1' },
          { id: `g${group.level}-r${roundId}-m3`, team1: [p[1], p[4]], team2: [p[2], p[3]], time: '09:40', courtNumber: '1' },
          { id: `g${group.level}-r${roundId}-m4`, team1: [p[0], p[2]], team2: [p[3], p[4]], time: '10:00', courtNumber: '1' },
          { id: `g${group.level}-r${roundId}-m5`, team1: [p[0], p[4]], team2: [p[1], p[3]], time: '10:20', courtNumber: '1' }
        ];

        matchesMap.set(group.level, matches);
        sittingMap.set(group.level, [[p[4]], [p[3]], [p[0]], [p[1]], [p[2]]]);
      } else if (group.players.length === 4) {
        const sorted = [...group.players].sort((a, b) => b.dupr_rating - a.dupr_rating);
        const p = sorted;

        const matches: MatchSlot[] = [
          { id: `g${group.level}-r${roundId}-m1`, team1: [p[0], p[1]], team2: [p[2], p[3]], time: '09:00', courtNumber: '1' },
          { id: `g${group.level}-r${roundId}-m2`, team1: [p[0], p[2]], team2: [p[1], p[3]], time: '09:20', courtNumber: '1' },
          { id: `g${group.level}-r${roundId}-m3`, team1: [p[0], p[3]], team2: [p[1], p[2]], time: '09:40', courtNumber: '1' },
        ];

        matchesMap.set(group.level, matches);
        sittingMap.set(group.level, [[], [], []]);
      }
    });

    this.roundsData.update(rounds => {
      const others = rounds.filter(r => r.roundId !== roundId);
      return [...others, { roundId, matches: matchesMap, sitting: sittingMap }].sort((a, b) => a.roundId - b.roundId);
    });
  }

  canGenerateSecondRoundOfDay(firstRoundId: number): boolean {
    const roundData = this.roundsData().find(r => r.roundId === firstRoundId);
    if (!roundData) return false;

    for (const [_, matches] of roundData.matches) {
      for (const m of matches) {
        if (m.score1 === undefined || m.score2 === undefined) return false;
      }
    }
    return true;
  }

  generateSecondRoundOfDay(firstRoundId: number) {
    const secondRoundId = firstRoundId + 1;
    const firstRoundData = this.roundsData().find(r => r.roundId === firstRoundId);
    if (!firstRoundData) return;

    const r2MatchesMap = new Map<number, MatchSlot[]>();
    const sittingMap = new Map<number, Player[][]>();

    for (const [level, matches] of firstRoundData.matches) {
      const uniquePlayersMap = new Map<string, Player>();
      matches.forEach(m => {
        m.team1.forEach(p => uniquePlayersMap.set(p.id, p));
        m.team2.forEach(p => uniquePlayersMap.set(p.id, p));
      });
      const sittingList = firstRoundData.sitting.get(level) || [];
      sittingList.forEach(s => {
        s.forEach(p => uniquePlayersMap.set(p.id, p));
      });
      const groupPlayers = Array.from(uniquePlayersMap.values());

      if (groupPlayers.length === 5) {
        const playerScores = new Map<string, number>();
        groupPlayers.forEach(p => playerScores.set(p.id, 0));

        matches.forEach(m => {
          m.team1.forEach(p => {
            const current = playerScores.get(p.id) || 0;
            playerScores.set(p.id, current + (m.score1 || 0));
          });
          m.team2.forEach(p => {
            const current = playerScores.get(p.id) || 0;
            playerScores.set(p.id, current + (m.score2 || 0));
          });
        });

        const rankedPlayers = [...groupPlayers].sort((a, b) => {
          const scoreA = playerScores.get(a.id) || 0;
          const scoreB = playerScores.get(b.id) || 0;
          if (scoreB !== scoreA) return scoreB - scoreA;
          return b.dupr_rating - a.dupr_rating; // Tie-break with DUPR
        });

        const match: MatchSlot = {
          id: `g${level}-r${secondRoundId}-m1`,
          team1: [rankedPlayers[0], rankedPlayers[4]],
          team2: [rankedPlayers[1], rankedPlayers[3]],
          time: '11:00',
          courtNumber: '1'
        };
        r2MatchesMap.set(level, [match]);
        sittingMap.set(level, [[rankedPlayers[2]]]);
      }
    }

    this.roundsData.update(rounds => {
      const others = rounds.filter(r => r.roundId !== secondRoundId);
      return [...others, { roundId: secondRoundId, matches: r2MatchesMap, sitting: sittingMap }].sort((a, b) => a.roundId - b.roundId);
    });
  }

  getGroupLevelsForRound(roundData: any): number[] {
    return Array.from((roundData.matches as Map<number, MatchSlot[]>).keys());
  }

  toggleGroup(roundId: number, level: number) {
    const key = `${roundId}-${level}`;
    this.collapsedGroups.update(set => {
      const newSet = new Set(set);
      if (newSet.has(key)) newSet.delete(key);
      else newSet.add(key);
      return newSet;
    });
  }

  isGroupCollapsed(roundId: number, level: number) {
    return this.collapsedGroups().has(`${roundId}-${level}`);
  }

  saveSlotting() {
    const league = this.league();
    if (!league) {
      console.error('No league found for ID/Name:', this.leagueId());
      console.log('Could not save: League information not found. Please try refreshing or going back to the league list.');
      return;
    }

    const rounds: RoundItem[] = [];

    for (const roundData of this.roundsData()) {
      const groups: GroupItem[] = [];
      for (const [level, matches] of roundData.matches) {
        const sittingList = roundData.sitting.get(level) || [];
        const sitting = sittingList[0]?.[0];
        const groupSize = (matches[0] ? matches[0].team1.length + matches[0].team2.length : 4) + (sitting ? 1 : 0);

        groups.push({
          group_id: level,
          group_name: `Group ${level}`,
          group_size: groupSize,
          match: matches.map((m, i) => {
             const mSitting = sittingList[i]?.[0];
             const mapPlayer = (p: Player) => ({
               firstName: p?.firstName || p?.name || '',
               lastName: p?.lastName || '',
               email: p?.email || ''
             });
             
             const matchItem: MatchItem = {
               match_id: m.id,
               league_id: league.league_id,
               league_name: league.league_name,
               round_id: roundData.roundId,
               group_id: level,
               team_one: {
                 team_id: `${m.id}-t1`,
                 team_name: 'Team 1',
                 player_one: mapPlayer(m.team1[0]),
                 player_two: mapPlayer(m.team1[1]),
                 score: m.score1 || 0
               },
               team_two: {
                 team_id: `${m.id}-t2`,
                 team_name: 'Team 2',
                 player_one: mapPlayer(m.team2[0]),
                 player_two: mapPlayer(m.team2[1]),
                 score: m.score2 || 0
               },
               time: `${this.slottingDate()}T${(m.time || '09:00')}:00`,
               court_number: m.courtNumber || '1'
             };

             if (mSitting) {
               matchItem.siting_player = mapPlayer(mSitting);
             }
             return matchItem;
          })
        });
      }
      rounds.push({ round_id: roundData.roundId, group: groups });
    }

    const payload: LeagueRoundPayload = {
      league_id: league.league_id,
      league_name: league.league_name,
      rounds: rounds
    };

    this.leagueService.saveRoundData(payload).subscribe({
      next: (res) => console.log('Slotting saved successfully!'),
      error: (err) => {
        console.error('Error saving slotting:', err);
        console.error('Error saving slotting:', JSON.stringify(err.error));
        console.log('Error saving slotting: ' + JSON.stringify(err.error));
      }
    });
  }

  saveRoundById(roundId: number) {
    const league = this.league();
    if (!league) return;

    const roundData = this.roundsData().find(r => r.roundId === roundId);
    if (!roundData) return;

    const groups: GroupItem[] = [];
    for (const [level, matches] of roundData.matches) {
      const sittingList = roundData.sitting.get(level) || [];
      const sitting = sittingList[0]?.[0];
      const groupSize = (matches[0] ? matches[0].team1.length + matches[0].team2.length : 4) + (sitting ? 1 : 0);

      groups.push({
        group_id: level,
        group_name: `Group ${level}`,
        group_size: groupSize,
        match: matches.map((m, i) => {
          const mSitting = sittingList[i]?.[0];
          const mapPlayer = (p: Player) => ({
            firstName: p?.firstName || p?.name || '',
            lastName: p?.lastName || '',
            email: p?.email || ''
          });

          const matchItem: MatchItem = {
            match_id: m.id,
            league_id: league.league_id,
            league_name: league.league_name,
            round_id: roundData.roundId,
            group_id: level,
            team_one: {
              team_id: `${m.id}-t1`,
              team_name: 'Team 1',
              player_one: mapPlayer(m.team1[0]),
              player_two: mapPlayer(m.team1[1]),
              score: m.score1 || 0
            },
            team_two: {
              team_id: `${m.id}-t2`,
              team_name: 'Team 2',
              player_one: mapPlayer(m.team2[0]),
              player_two: mapPlayer(m.team2[1]),
              score: m.score2 || 0
            },
            time: `${this.slottingDate()}T${(m.time || '09:00')}:00`,
            court_number: m.courtNumber || '1'
          };

          if (mSitting) {
            matchItem.siting_player = mapPlayer(mSitting);
          }
          return matchItem;
        })
      });
    }

    const payload: LeagueRoundPayload = {
      league_id: league.league_id,
      league_name: league.league_name,
      rounds: [{ round_id: roundData.roundId, group: groups }]
    };

    this.leagueService.saveRoundData(payload).subscribe({
      next: () => console.log(`Round ${roundId} saved successfully.`),
      error: (err) => console.error(`Error saving round ${roundId}:`, err)
    });
  }

  fetchExistingSlotting(leagueId: string) {
    this.http.get<LeagueDetailsPayload>(`/api/v1/league/name/${leagueId}`).subscribe({
      next: (data) => {
        // Ensure LeagueService has the correct players for this league
        if (data.players) {
          this.allLeaguePlayers.set(data.players);
          this.leagueWithdrawals.set(data.withdrawals || []);
          this.leagueStartDate.set(data.league_start_date || '');
          this.filterAndSetPlayers();
        }

        if (data.rounds && data.rounds.length > 0) {
          const loadedRounds: { roundId: number, matches: Map<number, MatchSlot[]>, sitting: Map<number, Player[][]> }[] = [];

          data.rounds.forEach(r => {
             const mMap = new Map<number, MatchSlot[]>();
             const sMap = new Map<number, Player[][]>();

             r.group.forEach((g: GroupItem) => {
                const level = g.group_id;
                const matches: MatchSlot[] = (g.match || []).map((m: MatchItem) => ({
                  id: m.match_id,
                  team1: [
                    this.findPlayer(m.team_one.player_one.email) || { ...m.team_one.player_one, id: m.team_one.player_one.email, name: m.team_one.player_one.firstName },
                    this.findPlayer(m.team_one.player_two.email) || { ...m.team_one.player_two, id: m.team_one.player_two.email, name: m.team_one.player_two.firstName }
                  ].filter(p => p && p.email) as Player[],
                  team2: [
                    this.findPlayer(m.team_two.player_one.email) || { ...m.team_two.player_one, id: m.team_two.player_one.email, name: m.team_two.player_one.firstName },
                    this.findPlayer(m.team_two.player_two.email) || { ...m.team_two.player_two, id: m.team_two.player_two.email, name: m.team_two.player_two.firstName }
                  ].filter(p => p && p.email) as Player[],
                  score1: m.team_one.score,
                  score2: m.team_two.score,
                  time: m.time.split('T')[1]?.substring(0, 5) || '09:00',
                  courtNumber: m.court_number
                }));
                mMap.set(level, matches);

                const sitting = (g.match || []).map((m: MatchItem) => m.siting_player ? [
                  this.findPlayer(m.siting_player.email) || { ...m.siting_player, id: m.siting_player.email, name: m.siting_player.firstName } as Player
                ] : []);
                sMap.set(level, sitting);
             });
             loadedRounds.push({ roundId: r.round_id, matches: mMap, sitting: sMap });
          });

          // Exclude rounds that have no matches (e.g. Round N+1 player-assignment data
          // created by promotion/relegation logic before the admin manually slots that round).
          const slottedRounds = loadedRounds.filter(round => {
            for (const matches of round.matches.values()) {
              if (matches.length > 0) return true;
            }
            return false;
          });
          this.roundsData.set(slottedRounds.sort((a,b) => a.roundId - b.roundId));
        } else {
          // No existing rounds found in DB.
          this.roundsData.set([]);
        }
      },
      error: (err) => console.error('Error fetching existing slotting:', err)
    });
  }

  private findPlayer(email: string): Player | undefined {
    return this.allLeaguePlayers().find(p => p.email === email);
  }
}
