"""Pure functions that turn a flat list of registered entrants (individual
players for singles, pairs for doubles) into a round-robin-pools + knockout
tournament structure.

Kept free of any DB / IO so it can be unit tested in isolation.
"""
import math
import uuid
from typing import List

from app.vo.pb.player import Player
from app.vo.pb.tournament import KnockoutMatch, KnockoutRound, Pool, PoolMatch
from app.vo.pb.tournament_team import TournamentTeam

_POOL_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_ORDINALS = {1: "1st", 2: "2nd", 3: "3rd"}


def _ordinal(n: int) -> str:
    return _ORDINALS.get(n, f"{n}th")


def _entrant_rating(entrant) -> float:
    return getattr(entrant, "dupr_rating", None) or 0.0


def _entrant_key(entrant) -> str:
    return getattr(entrant, "email", None) or getattr(entrant, "team_id", "")


def _entrant_name(entrant) -> str:
    name = getattr(entrant, "team_name", None)
    if name:
        return name
    return f"{getattr(entrant, 'firstName', '')} {getattr(entrant, 'lastName', '')}".strip()


def _round_name(num_matches: int) -> str:
    return {1: "Final", 2: "Semifinal", 4: "Quarterfinal"}.get(
        num_matches, f"Round of {num_matches * 2}"
    )


def _seeding_order(size: int) -> List[int]:
    """Standard single-elimination bracket seeding order for a power-of-two size.

    e.g. size 4 -> [1, 4, 2, 3], size 8 -> [1, 8, 4, 5, 2, 7, 3, 6].
    Consecutive pairs are the first-round matchups.
    """
    order = [1, 2]
    while len(order) < size:
        pair_sum = len(order) * 2 + 1
        expanded: List[int] = []
        for seed in order:
            expanded.append(seed)
            expanded.append(pair_sum - seed)
        order = expanded
    return order


def _seed_into_pools(entrants: list, pool_size: int):
    """Seed entrants by DUPR rating and serpentine-draft them into balanced
    pools, then generate the round-robin matches.

    Returns ``(pools, buckets)`` where ``buckets[i]`` is the ordered list of
    entrant objects for ``pools[i]`` — the caller places them onto
    ``pool.players`` (singles) or ``pool.teams`` (doubles).
    """
    seeded = sorted(entrants, key=_entrant_rating, reverse=True)
    if not seeded:
        return [], []

    num_pools = max(1, math.ceil(len(seeded) / pool_size))
    num_pools = min(num_pools, len(_POOL_LABELS))
    pools = [
        Pool(pool_id=i + 1, pool_name=f"Pool {_POOL_LABELS[i]}")
        for i in range(num_pools)
    ]
    buckets: List[list] = [[] for _ in range(num_pools)]

    idx, direction = 0, 1
    for entrant in seeded:
        buckets[idx].append(entrant)
        if direction == 1 and idx == num_pools - 1:
            direction = -1
        elif direction == -1 and idx == 0:
            direction = 1
        else:
            idx += direction

    for pool, bucket in zip(pools, buckets):
        for a in range(len(bucket)):
            for b in range(a + 1, len(bucket)):
                e1, e2 = bucket[a], bucket[b]
                pool.matches.append(
                    PoolMatch(
                        match_id=str(uuid.uuid4()),
                        pool_id=pool.pool_id,
                        participant_one_email=_entrant_key(e1),
                        participant_one_name=_entrant_name(e1),
                        participant_two_email=_entrant_key(e2),
                        participant_two_name=_entrant_name(e2),
                    )
                )
    return pools, buckets


def build_pools(players: List[Player], pool_size: int) -> List[Pool]:
    """Seed individual players into round-robin pools (singles tournaments)."""
    pools, buckets = _seed_into_pools(players, pool_size)
    for pool, bucket in zip(pools, buckets):
        pool.players = list(bucket)
    return pools


def build_team_pools(teams: List[TournamentTeam], pool_size: int) -> List[Pool]:
    """Seed doubles teams into round-robin pools (doubles tournaments)."""
    pools, buckets = _seed_into_pools(teams, pool_size)
    for pool, bucket in zip(pools, buckets):
        pool.teams = list(bucket)
    return pools


def build_knockout(num_pools: int, advancers_per_pool: int) -> List[KnockoutRound]:
    """Build the knockout bracket skeleton that the pool qualifiers feed into.

    Qualifiers are seeded pool-rank first (all pool winners, then all
    runners-up, ...). The bracket is padded with byes up to the next power
    of two.
    """
    qualifiers = num_pools * advancers_per_pool
    if qualifiers < 2:
        return []

    size = 1
    while size < qualifiers:
        size <<= 1

    # seed number -> descriptive label ("bye" for padded seeds)
    seed_labels = {}
    seed = 1
    for rank in range(1, advancers_per_pool + 1):
        for pool_idx in range(num_pools):
            seed_labels[seed] = f"{_ordinal(rank)} Pool {_POOL_LABELS[pool_idx]}"
            seed += 1
    for extra in range(qualifiers + 1, size + 1):
        seed_labels[extra] = "Bye"

    order = _seeding_order(size)
    rounds: List[KnockoutRound] = []

    first_matches: List[KnockoutMatch] = []
    for i in range(0, size, 2):
        first_matches.append(
            KnockoutMatch(
                match_id=str(uuid.uuid4()),
                slot_one_label=seed_labels[order[i]],
                slot_two_label=seed_labels[order[i + 1]],
            )
        )
    rounds.append(
        KnockoutRound(round_id=1, round_name=_round_name(len(first_matches)), matches=first_matches)
    )

    prev = first_matches
    round_id = 1
    while len(prev) > 1:
        round_id += 1
        matches: List[KnockoutMatch] = []
        for i in range(0, len(prev), 2):
            matches.append(
                KnockoutMatch(
                    match_id=str(uuid.uuid4()),
                    slot_one_label=f"Winner R{round_id - 1} M{i + 1}",
                    slot_two_label=f"Winner R{round_id - 1} M{i + 2}",
                )
            )
        rounds.append(
            KnockoutRound(round_id=round_id, round_name=_round_name(len(matches)), matches=matches)
        )
        prev = matches

    return rounds


# --------------------------------------------------------------------- scoring
#
# The functions below advance a drawn tournament as results come in. They stay
# pure (mutate the passed-in Pydantic models, no IO) so the service layer can
# load, hand them the models, and persist the result.

_DONE_STATUSES = ("Completed", "Bye")


def _match_winner(match):
    """``(email, name)`` of the winner of a finished match, or ``None``."""
    if match.match_status not in _DONE_STATUSES or match.score_one == match.score_two:
        return None
    if match.score_one > match.score_two:
        return match.participant_one_email, match.participant_one_name
    return match.participant_two_email, match.participant_two_name


def _clear_result(match) -> None:
    match.score_one = 0
    match.score_two = 0
    match.match_status = "YetToPlay"


def pool_is_complete(pool) -> bool:
    return bool(pool.matches) and all(
        m.match_status in _DONE_STATUSES for m in pool.matches
    )


def pool_standings(pool):
    """Rank a pool's entrants best-first by wins, then point differential, then
    points scored. Only counts matches that have been played.

    Returns a list of ``(email, name)`` tuples.
    """
    stats: dict = {}  # email -> [wins, diff, points_for, name]
    for m in pool.matches:
        if m.match_status not in _DONE_STATUSES:
            continue
        for email, name, gf, ga in (
            (m.participant_one_email, m.participant_one_name, m.score_one, m.score_two),
            (m.participant_two_email, m.participant_two_name, m.score_two, m.score_one),
        ):
            if not email:
                continue
            row = stats.setdefault(email, [0, 0, 0, name])
            row[0] += 1 if gf > ga else 0
            row[1] += gf - ga
            row[2] += gf
    ranked = sorted(stats.items(), key=lambda kv: tuple(kv[1][:3]), reverse=True)
    return [(email, row[3]) for email, row in ranked]


def _assign_slot(match, into_one: bool, email, name) -> bool:
    """Put an entrant into a bracket slot. Returns True if it changed anything
    (and resets that match's result when it did, so a corrected earlier result
    doesn't leave a stale downstream score behind)."""
    current = match.participant_one_email if into_one else match.participant_two_email
    if current == email:
        return False
    if into_one:
        match.participant_one_email, match.participant_one_name = email, name
    else:
        match.participant_two_email, match.participant_two_name = email, name
    _clear_result(match)
    return True


def resolve_pool_qualifiers(pools, rounds, advancers_per_pool: int) -> None:
    """Fill the first knockout round with the real qualifiers from every pool
    that has finished, matching them to their seed labels ("1st Pool A", ...)."""
    if not rounds:
        return
    first = rounds[0].matches
    for pool_idx, pool in enumerate(pools):
        if pool_idx >= len(_POOL_LABELS) or not pool_is_complete(pool):
            continue
        standings = pool_standings(pool)
        letter = _POOL_LABELS[pool_idx]
        for rank in range(1, advancers_per_pool + 1):
            if rank > len(standings):
                break
            email, name = standings[rank - 1]
            label = f"{_ordinal(rank)} Pool {letter}"
            for m in first:
                if m.slot_one_label == label:
                    _assign_slot(m, True, email, name)
                elif m.slot_two_label == label:
                    _assign_slot(m, False, email, name)


def advance_knockout(rounds) -> None:
    """Walk the bracket, auto-completing byes and carrying each finished match's
    winner into the next round. Idempotent — safe to run after every result."""
    for r in range(len(rounds)):
        for i, m in enumerate(rounds[r].matches):
            _autocomplete_bye(m)
            if r + 1 >= len(rounds):
                continue
            nxt = rounds[r + 1].matches[i // 2]
            win = _match_winner(m)
            email, name = win if win else (None, None)
            _assign_slot(nxt, i % 2 == 0, email, name)


def _autocomplete_bye(match) -> None:
    """A first-round match with a real entrant on one side and a "Bye" on the
    other resolves itself the moment the entrant is known."""
    if match.match_status in _DONE_STATUSES:
        return
    one, two = bool(match.participant_one_email), bool(match.participant_two_email)
    if one and not two and match.slot_two_label == "Bye":
        match.score_one, match.score_two, match.match_status = 1, 0, "Bye"
    elif two and not one and match.slot_one_label == "Bye":
        match.score_one, match.score_two, match.match_status = 0, 1, "Bye"


def knockout_is_complete(rounds) -> bool:
    return bool(rounds) and all(
        m.match_status in _DONE_STATUSES for m in rounds[-1].matches
    )
