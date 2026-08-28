"""Pure functions that turn a flat list of registered players into a
round-robin-pools + knockout tournament structure.

Kept free of any DB / IO so it can be unit tested in isolation.
"""
import math
import uuid
from typing import List

from app.vo.pb.player import Player
from app.vo.pb.tournament import KnockoutMatch, KnockoutRound, Pool, PoolMatch

_POOL_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_ORDINALS = {1: "1st", 2: "2nd", 3: "3rd"}


def _ordinal(n: int) -> str:
    return _ORDINALS.get(n, f"{n}th")


def _player_name(player: Player) -> str:
    return f"{player.firstName} {player.lastName}".strip()


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


def build_pools(players: List[Player], pool_size: int) -> List[Pool]:
    """Seed players by DUPR rating and distribute them across balanced pools
    using a serpentine (snake) draft, then generate the round-robin matches.
    """
    seeded = sorted(players, key=lambda p: (p.dupr_rating or 0.0), reverse=True)
    if not seeded:
        return []

    num_pools = max(1, math.ceil(len(seeded) / pool_size))
    num_pools = min(num_pools, len(_POOL_LABELS))
    pools = [
        Pool(pool_id=i + 1, pool_name=f"Pool {_POOL_LABELS[i]}")
        for i in range(num_pools)
    ]

    idx, direction = 0, 1
    for player in seeded:
        pools[idx].players.append(player)
        if direction == 1 and idx == num_pools - 1:
            direction = -1
        elif direction == -1 and idx == 0:
            direction = 1
        else:
            idx += direction

    for pool in pools:
        n = len(pool.players)
        for a in range(n):
            for b in range(a + 1, n):
                p1, p2 = pool.players[a], pool.players[b]
                pool.matches.append(
                    PoolMatch(
                        match_id=str(uuid.uuid4()),
                        pool_id=pool.pool_id,
                        participant_one_email=p1.email,
                        participant_one_name=_player_name(p1),
                        participant_two_email=p2.email,
                        participant_two_name=_player_name(p2),
                    )
                )
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
