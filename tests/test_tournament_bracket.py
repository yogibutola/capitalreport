import unittest

from app.services.tournament_bracket import build_knockout, build_pools
from app.vo.pb.player import Player


def _players(n: int) -> list[Player]:
    return [
        Player(
            firstName=f"P{i}",
            lastName="Test",
            email=f"p{i}@e.com",
            dupr_rating=float(n - i),  # p1 strongest
        )
        for i in range(1, n + 1)
    ]


class TestBuildPools(unittest.TestCase):
    def test_pool_count_and_sizes(self):
        pools = build_pools(_players(16), pool_size=4)
        self.assertEqual(len(pools), 4)
        self.assertEqual(sorted(len(p.players) for p in pools), [4, 4, 4, 4])

    def test_serpentine_balances_top_seeds(self):
        pools = build_pools(_players(16), pool_size=4)
        # top 4 seeds should each land in a different pool
        top_emails = {"p1@e.com", "p2@e.com", "p3@e.com", "p4@e.com"}
        pools_with_top = [
            p for p in pools if any(pl.email in top_emails for pl in p.players)
        ]
        self.assertEqual(len(pools_with_top), 4)

    def test_round_robin_match_count(self):
        pools = build_pools(_players(15), pool_size=4)  # 4 pools: 4,4,4,3
        for pool in pools:
            n = len(pool.players)
            self.assertEqual(len(pool.matches), n * (n - 1) // 2)

    def test_empty(self):
        self.assertEqual(build_pools([], pool_size=4), [])


class TestBuildKnockout(unittest.TestCase):
    def test_two_pools_two_advancers_is_semifinal_plus_final(self):
        rounds = build_knockout(num_pools=2, advancers_per_pool=2)
        self.assertEqual([r.round_name for r in rounds], ["Semifinal", "Final"])
        self.assertEqual(len(rounds[0].matches), 2)
        self.assertEqual(len(rounds[1].matches), 1)

    def test_cross_seeding_first_round(self):
        rounds = build_knockout(num_pools=2, advancers_per_pool=2)
        labels = {
            (m.slot_one_label, m.slot_two_label) for m in rounds[0].matches
        }
        self.assertEqual(
            labels, {("1st Pool A", "2nd Pool B"), ("1st Pool B", "2nd Pool A")}
        )

    def test_byes_padded_to_power_of_two(self):
        rounds = build_knockout(num_pools=3, advancers_per_pool=2)  # 6 qualifiers -> 8
        self.assertEqual(len(rounds[0].matches), 4)
        bye_slots = [
            s
            for m in rounds[0].matches
            for s in (m.slot_one_label, m.slot_two_label)
            if s == "Bye"
        ]
        self.assertEqual(len(bye_slots), 2)

    def test_no_bracket_when_single_qualifier(self):
        self.assertEqual(build_knockout(num_pools=1, advancers_per_pool=1), [])


if __name__ == "__main__":
    unittest.main()
