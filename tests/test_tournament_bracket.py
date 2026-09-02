import unittest

from app.services.tournament_bracket import (
    advance_knockout,
    build_knockout,
    build_pools,
    build_team_pools,
    knockout_is_complete,
    pool_standings,
    resolve_pool_qualifiers,
)
from app.vo.pb.player import Player
from app.vo.pb.tournament import Pool, PoolMatch
from app.vo.pb.tournament_team import TournamentTeam


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


def _teams(n: int) -> list[TournamentTeam]:
    return [
        TournamentTeam(
            team_id=f"t{i}",
            team_name=f"Team {i}",
            player_one_email=f"a{i}@e.com",
            player_one_name=f"A{i}",
            player_two_email=f"b{i}@e.com",
            player_two_name=f"B{i}",
            dupr_rating=float(n - i),  # t1 strongest
        )
        for i in range(1, n + 1)
    ]


class TestBuildTeamPools(unittest.TestCase):
    def test_teams_seeded_into_pools(self):
        pools = build_team_pools(_teams(12), pool_size=4)
        self.assertEqual(len(pools), 3)
        self.assertEqual(sorted(len(p.teams) for p in pools), [4, 4, 4])
        # no individual players on a doubles pool
        self.assertTrue(all(p.players == [] for p in pools))

    def test_serpentine_balances_top_team_seeds(self):
        pools = build_team_pools(_teams(12), pool_size=4)
        top = {"t1", "t2", "t3"}
        pools_with_top = [
            p for p in pools if any(tm.team_id in top for tm in p.teams)
        ]
        self.assertEqual(len(pools_with_top), 3)

    def test_round_robin_matches_reference_team_ids(self):
        pools = build_team_pools(_teams(8), pool_size=4)
        for pool in pools:
            n = len(pool.teams)
            self.assertEqual(len(pool.matches), n * (n - 1) // 2)
            ids = {tm.team_id for tm in pool.teams}
            for m in pool.matches:
                self.assertIn(m.participant_one_email, ids)
                self.assertIn(m.participant_two_email, ids)

    def test_empty(self):
        self.assertEqual(build_team_pools([], pool_size=4), [])


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


def _pm(one, two, s1=0, s2=0, played=False) -> PoolMatch:
    return PoolMatch(
        match_id=f"{one}-{two}",
        pool_id=1,
        participant_one_email=f"{one}@e.com",
        participant_one_name=one,
        participant_two_email=f"{two}@e.com",
        participant_two_name=two,
        score_one=s1,
        score_two=s2,
        match_status="Completed" if played else "YetToPlay",
    )


class TestPoolStandings(unittest.TestCase):
    def test_ranks_by_wins_then_diff_then_points(self):
        pool = Pool(
            pool_id=1,
            pool_name="Pool A",
            matches=[
                _pm("A", "B", 11, 5, played=True),
                _pm("A", "C", 11, 9, played=True),
                _pm("B", "C", 11, 7, played=True),
            ],
        )
        order = [name for _, name in pool_standings(pool)]
        self.assertEqual(order, ["A", "B", "C"])

    def test_ignores_unplayed_matches(self):
        pool = Pool(
            pool_id=1,
            pool_name="Pool A",
            matches=[_pm("A", "B", 11, 5, played=True), _pm("A", "C")],
        )
        self.assertEqual([n for _, n in pool_standings(pool)], ["A", "B"])


class TestResolvePoolQualifiers(unittest.TestCase):
    def _two_pool_bracket(self):
        return build_knockout(num_pools=2, advancers_per_pool=2)

    def test_fills_first_round_from_finished_pools(self):
        rounds = self._two_pool_bracket()
        pool_a = Pool(
            pool_id=1, pool_name="Pool A",
            matches=[_pm("A1", "A2", 11, 3, played=True)],
        )
        pool_b = Pool(
            pool_id=2, pool_name="Pool B",
            matches=[_pm("B1", "B2", 11, 6, played=True)],
        )
        resolve_pool_qualifiers([pool_a, pool_b], rounds, advancers_per_pool=2)

        slots = {
            (m.participant_one_name, m.participant_two_name) for m in rounds[0].matches
        }
        # 1st Pool A vs 2nd Pool B, and 1st Pool B vs 2nd Pool A
        self.assertEqual(slots, {("A1", "B2"), ("B1", "A2")})

    def test_incomplete_pool_leaves_labels(self):
        rounds = self._two_pool_bracket()
        pool_a = Pool(pool_id=1, pool_name="Pool A", matches=[_pm("A1", "A2")])
        pool_b = Pool(pool_id=2, pool_name="Pool B", matches=[_pm("B1", "B2")])
        resolve_pool_qualifiers([pool_a, pool_b], rounds, advancers_per_pool=2)
        self.assertTrue(
            all(m.participant_one_email is None for m in rounds[0].matches)
        )


class TestAdvanceKnockout(unittest.TestCase):
    def _semis_and_final(self):
        rounds = build_knockout(num_pools=2, advancers_per_pool=2)
        for i, m in enumerate(rounds[0].matches):
            m.participant_one_email, m.participant_one_name = f"p{2*i}", f"P{2*i}"
            m.participant_two_email, m.participant_two_name = f"p{2*i+1}", f"P{2*i+1}"
        return rounds

    def test_winner_carries_into_final(self):
        rounds = self._semis_and_final()
        rounds[0].matches[0].score_one = 11
        rounds[0].matches[0].score_two = 4
        rounds[0].matches[0].match_status = "Completed"
        advance_knockout(rounds)
        self.assertEqual(rounds[1].matches[0].participant_one_name, "P0")
        self.assertIsNone(rounds[1].matches[0].participant_two_email)
        self.assertFalse(knockout_is_complete(rounds))

    def test_correcting_a_result_updates_the_final(self):
        rounds = self._semis_and_final()
        sf = rounds[0].matches[0]
        sf.score_one, sf.score_two, sf.match_status = 11, 4, "Completed"
        advance_knockout(rounds)
        # admin flips the result
        sf.score_one, sf.score_two = 4, 11
        advance_knockout(rounds)
        self.assertEqual(rounds[1].matches[0].participant_one_name, "P1")

    def test_bye_auto_advances_once_entrant_known(self):
        rounds = build_knockout(num_pools=3, advancers_per_pool=2)  # 6 -> 8, 2 byes
        bye_match = next(
            m for m in rounds[0].matches if "Bye" in (m.slot_one_label, m.slot_two_label)
        )
        real_side_one = bye_match.slot_two_label == "Bye"
        if real_side_one:
            bye_match.participant_one_email, bye_match.participant_one_name = "x", "X"
        else:
            bye_match.participant_two_email, bye_match.participant_two_name = "x", "X"
        advance_knockout(rounds)
        self.assertEqual(bye_match.match_status, "Bye")
        idx = rounds[0].matches.index(bye_match)
        nxt = rounds[1].matches[idx // 2]
        carried = nxt.participant_one_name if idx % 2 == 0 else nxt.participant_two_name
        self.assertEqual(carried, "X")


if __name__ == "__main__":
    unittest.main()
