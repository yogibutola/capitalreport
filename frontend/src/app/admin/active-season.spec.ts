import { describe, expect, it } from 'vitest';
import { isActiveStatus, summarizeLeague } from './season-progress';
import { isLeaguesUrl, isTournamentsUrl } from '../nav-urls';
import type { MatchItem } from '../league/league';

function match(round_id: number, match_status?: string): MatchItem {
  return {
    match_id: `m-${round_id}-${Math.random()}`,
    league_id: 'L1',
    league_name: 'Spring',
    round_id,
    group_id: 1,
    team_one: { team_id: 't1', team_name: 'A', player_one: {} as any, player_two: {} as any, score: 0 },
    team_two: { team_id: 't2', team_name: 'B', player_one: {} as any, player_two: {} as any, score: 0 },
    match_status,
    time: '',
    court_number: '',
  };
}

describe('isActiveStatus', () => {
  it('matches active regardless of case or whitespace', () => {
    expect(isActiveStatus('active')).toBe(true);
    expect(isActiveStatus('Active')).toBe(true);
    expect(isActiveStatus(' ACTIVE ')).toBe(true);
  });

  it('rejects pending, empty and missing statuses', () => {
    expect(isActiveStatus('pending')).toBe(false);
    expect(isActiveStatus('')).toBe(false);
    expect(isActiveStatus(null)).toBe(false);
    expect(isActiveStatus(undefined)).toBe(false);
  });
});

describe('summarizeLeague', () => {
  it('reports an unslotted league with no round or matches', () => {
    const p = summarizeLeague({ players: [{} as any, {} as any, {} as any] });
    expect(p.playerCount).toBe(3);
    expect(p.roundsSlotted).toBe(0);
    expect(p.currentRound).toBeNull();
    expect(p.playDay).toBeNull();
    expect(p.matchesTotal).toBe(0);
    expect(p.matchesPending).toBe(0);
    expect(p.currentRoundPending).toBe(0);
  });

  it('derives the current round, play day and match progress from matches', () => {
    const p = summarizeLeague({
      rounds: [{ round_id: 1, group: [] }, { round_id: 2, group: [] }, { round_id: 3, group: [] }],
      matches: [
        match(1, 'completed'),
        match(1, 'completed'),
        match(2, 'completed'),
        match(2, 'YetToPlay'),
        match(3),
        match(3, 'YetToPlay'),
      ],
    });
    expect(p.roundsSlotted).toBe(3);
    expect(p.currentRound).toBe(3);
    expect(p.playDay).toBe(2); // (3 + 1) // 2
    expect(p.matchesTotal).toBe(6);
    expect(p.matchesCompleted).toBe(3);
    expect(p.matchesPending).toBe(3);
    expect(p.currentRoundPending).toBe(2);
  });

  it('uses slotted rounds for the current round when matches have not been split out yet', () => {
    const p = summarizeLeague({ rounds: [{ round_id: 1, group: [] }, { round_id: 2, group: [] }] });
    expect(p.currentRound).toBe(2);
    expect(p.playDay).toBe(1);
  });

  it('treats completion status case-insensitively and passes dates/location through', () => {
    const p = summarizeLeague({
      matches: [match(1, 'Completed'), match(1, 'COMPLETED'), match(1)],
      league_start_date: '03-01-2026',
      league_end_date: '04-12-2026',
      location: 'Court 4',
    });
    expect(p.matchesCompleted).toBe(2);
    expect(p.startDate).toBe('03-01-2026');
    expect(p.endDate).toBe('04-12-2026');
    expect(p.location).toBe('Court 4');
  });
});

describe('isLeaguesUrl / isTournamentsUrl (club nav highlighting)', () => {
  it('lights up Leagues for the list, create form, and league detail pages', () => {
    expect(isLeaguesUrl('/admin/leagues')).toBe(true);
    expect(isLeaguesUrl('/admin/leagues?x=1')).toBe(true);
    expect(isLeaguesUrl('/admin/create-league')).toBe(true);
    expect(isLeaguesUrl('/admin/league/Spring%20Ladder')).toBe(true);
  });

  it('lights up Tournaments for the list, create form, and tournament detail pages', () => {
    expect(isTournamentsUrl('/admin/tournaments')).toBe(true);
    expect(isTournamentsUrl('/admin/tournaments#top')).toBe(true);
    expect(isTournamentsUrl('/admin/create-tournament')).toBe(true);
    expect(isTournamentsUrl('/admin/tournament/abc123')).toBe(true);
  });

  it('never lights up both tabs, and neither on bare /admin (pre-redirect) or the season tab', () => {
    for (const url of ['/admin', '/admin/season', '/profile', '/', '/player/leagues', '/player/tournaments']) {
      expect(isLeaguesUrl(url)).toBe(false);
      expect(isTournamentsUrl(url)).toBe(false);
    }
    expect(isTournamentsUrl('/admin/leagues')).toBe(false);
    expect(isTournamentsUrl('/admin/league/x')).toBe(false);
    expect(isLeaguesUrl('/admin/tournaments')).toBe(false);
    expect(isLeaguesUrl('/admin/tournament/x')).toBe(false);
  });
});
