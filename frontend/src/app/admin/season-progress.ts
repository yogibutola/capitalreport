import type { LeagueDetailsPayload, MatchItem } from '../league/league';

/**
 * Pure helpers behind the club "Active Season" page. No Angular imports so they
 * can be unit-tested with plain vitest.
 */

/** Status values are stored inconsistently ("active" vs "Active"); compare loosely. */
export function isActiveStatus(status: string | null | undefined): boolean {
  return (status ?? '').trim().toLowerCase() === 'active';
}

/** Per-league progress snapshot derived from the full league payload. */
export interface LeagueProgress {
  playerCount: number;
  roundsSlotted: number;
  /** Highest round that has been slotted (with or without matches), or null if none. */
  currentRound: number | null;
  /** Two rounds per play day: play_day = (round + 1) // 2. */
  playDay: number | null;
  matchesTotal: number;
  matchesCompleted: number;
  matchesPending: number;
  /** Matches still to be played in the current round. */
  currentRoundPending: number;
  startDate?: string;
  endDate?: string;
  location?: string;
}

export type LeagueDetailsWithMatches = Partial<LeagueDetailsPayload> & { matches?: MatchItem[] };

function isCompleted(match: MatchItem): boolean {
  return (match.match_status ?? '').toLowerCase() === 'completed';
}

export function summarizeLeague(data: LeagueDetailsWithMatches): LeagueProgress {
  const rounds = data.rounds ?? [];
  const matches = data.matches ?? [];

  const roundIds = [
    ...rounds.map((r) => Number(r.round_id)),
    ...matches.map((m) => Number(m.round_id)),
  ].filter((n) => Number.isFinite(n) && n > 0);
  const currentRound = roundIds.length ? Math.max(...roundIds) : null;

  const completed = matches.filter(isCompleted).length;
  const currentRoundMatches =
    currentRound === null ? [] : matches.filter((m) => Number(m.round_id) === currentRound);

  return {
    playerCount: data.players?.length ?? 0,
    roundsSlotted: rounds.length,
    currentRound,
    playDay: currentRound === null ? null : Math.floor((currentRound + 1) / 2),
    matchesTotal: matches.length,
    matchesCompleted: completed,
    matchesPending: matches.length - completed,
    currentRoundPending: currentRoundMatches.filter((m) => !isCompleted(m)).length,
    startDate: data.league_start_date,
    endDate: data.league_end_date,
    location: data.location,
  };
}
