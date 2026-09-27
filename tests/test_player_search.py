import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.services.pb_player_service import PBPlayerService
from app.utils.geo import Coordinates

SEARCHER = "me@example.com"

# A few places with known separations, so a radius test reads as geography
# rather than arithmetic. Distances from ASHBURN: DC ~26mi, RICHMOND ~90mi.
ASHBURN = Coordinates(39.0373, -77.4805)
STERLING = Coordinates(39.0062, -77.4286)   # ~4 mi from Ashburn
DC = Coordinates(38.9072, -77.0369)         # ~26 mi
RICHMOND = Coordinates(37.5407, -77.4360)   # ~103 mi

ZIP_COORDS = {
    "20147": ASHBURN,
    "20164": STERLING,
    "20001": DC,
    "23219": RICHMOND,
}


def player(email, first="Bea", last="Baker", rating=4.0, zip_code="20164", **extra):
    return {"_id": f"id-{email}", "email": email, "firstName": first,
            "lastName": last, "dupr_rating": rating, "role": "player",
            "city": None, "state": None, "zip_code": zip_code, **extra}


def fake_geocode(zip_code):
    """Stand-in for coordinates_for_zip: only the ZIPs above are placeable."""
    return ZIP_COORDS.get(zip_code)


class PlayerSearchTestCase(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.service = PBPlayerService(self.mock_store)
        self.mock_store.find_players.return_value = []
        # The searcher lives in Ashburn unless a test says otherwise.
        self.mock_store.find_player_by_email.return_value = player(
            SEARCHER, first="Ada", last="Lovelace", zip_code="20147")

    def search(self, **kwargs):
        with patch('app.services.pb_player_service.coordinates_for_zip', side_effect=fake_geocode):
            return self.service.search_players(searcher_email=SEARCHER, **kwargs)


class TestFiltersArePushedToMongo(PlayerSearchTestCase):
    """Name and rating filters belong in the query, not in a Python loop."""

    def test_name_and_rating_filters_reach_the_store(self):
        self.search(first_name="bea", last_name="bak", dupr_min=3.5, dupr_max=4.5)
        kwargs = self.mock_store.find_players.call_args.kwargs
        self.assertEqual(kwargs["first_name"], "bea")
        self.assertEqual(kwargs["last_name"], "bak")
        self.assertEqual(kwargs["dupr_min"], 3.5)
        self.assertEqual(kwargs["dupr_max"], 4.5)

    def test_the_searcher_is_excluded_from_their_own_results(self):
        self.search(first_name="a")
        self.assertEqual(self.mock_store.find_players.call_args.kwargs["exclude_email"], SEARCHER)


class TestDuprRange(PlayerSearchTestCase):
    def test_inverted_range_is_a_400_with_a_code(self):
        with self.assertRaises(HTTPException) as ctx:
            self.search(dupr_min=4.5, dupr_max=3.0)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["code"], "dupr_range_inverted")

    def test_equal_bounds_are_allowed(self):
        self.search(dupr_min=4.0, dupr_max=4.0)  # a single-rating search is legitimate
        self.mock_store.find_players.assert_called_once()

    def test_a_rating_less_player_is_dropped_by_the_mongo_query_not_here(self):
        """The $gte/$lte on dupr_rating already excludes missing/null ratings, so
        the service must not need a second filter - it just passes the bounds."""
        self.search(dupr_min=3.0)
        self.assertEqual(self.mock_store.find_players.call_args.kwargs["dupr_min"], 3.0)


class TestNoRadius(PlayerSearchTestCase):
    def test_distance_is_none_on_every_row(self):
        self.mock_store.find_players.return_value = [
            player("a@x.com", zip_code="20164"), player("b@x.com", zip_code=None)]
        resp = self.search(first_name="b")
        self.assertEqual(len(resp.results), 2)
        self.assertTrue(all(r.distance_miles is None for r in resp.results))
        self.assertIsNone(resp.radius_miles)

    def test_unplaceable_players_are_kept_when_no_radius_is_set(self):
        """Location only gates results when the searcher actually asked about it."""
        self.mock_store.find_players.return_value = [player("nozip@x.com", zip_code=None)]
        self.assertEqual(len(self.search(first_name="b").results), 1)

    def test_results_are_sorted_by_name(self):
        self.mock_store.find_players.return_value = [
            player("c@x.com", first="Cara", last="Zane"),
            player("a@x.com", first="Abe", last="Adams"),
            player("b@x.com", first="Bo", last="Mills"),
        ]
        resp = self.search(first_name="")
        self.assertEqual([r.lastName for r in resp.results], ["Adams", "Mills", "Zane"])


class TestRadius(PlayerSearchTestCase):
    def test_players_outside_the_radius_are_dropped(self):
        self.mock_store.find_players.return_value = [
            player("close@x.com", zip_code="20164"),    # ~4 mi
            player("far@x.com", zip_code="23219"),      # ~103 mi
        ]
        resp = self.search(radius_miles=25)
        self.assertEqual([r.email for r in resp.results], ["close@x.com"])

    def test_distance_is_rounded_to_one_decimal(self):
        self.mock_store.find_players.return_value = [player("close@x.com", zip_code="20164")]
        miles = self.search(radius_miles=25).results[0].distance_miles
        self.assertEqual(miles, round(miles, 1))
        self.assertAlmostEqual(miles, 4.0, delta=1.5)

    def test_a_player_with_no_zip_is_dropped(self):
        self.mock_store.find_players.return_value = [
            player("nozip@x.com", zip_code=None), player("close@x.com", zip_code="20164")]
        resp = self.search(radius_miles=50)
        self.assertEqual([r.email for r in resp.results], ["close@x.com"])

    def test_a_player_with_an_unknown_zip_is_dropped(self):
        self.mock_store.find_players.return_value = [player("bad@x.com", zip_code="00000")]
        self.assertEqual(self.search(radius_miles=500).results, [])

    def test_results_are_sorted_nearest_first(self):
        self.mock_store.find_players.return_value = [
            player("dc@x.com", zip_code="20001"),       # ~26 mi
            player("rva@x.com", zip_code="23219"),      # ~103 mi
            player("sterling@x.com", zip_code="20164"), # ~4 mi
        ]
        resp = self.search(radius_miles=200)
        self.assertEqual([r.email for r in resp.results],
                         ["sterling@x.com", "dc@x.com", "rva@x.com"])

    def test_the_radius_is_echoed_back(self):
        resp = self.search(radius_miles=25)
        self.assertEqual(resp.radius_miles, 25)
        self.assertEqual(resp.origin_zip, "20147")


class TestSearchOrigin(PlayerSearchTestCase):
    def test_origin_zip_overrides_the_profile_zip(self):
        """Searching around somewhere else: a club across town, or a trip."""
        self.mock_store.find_players.return_value = [player("rva@x.com", zip_code="23219")]
        # Richmond is ~103mi from the searcher's Ashburn home, but 0mi from Richmond.
        resp = self.search(radius_miles=10, origin_zip="23219")
        self.assertEqual(resp.origin_zip, "23219")
        self.assertEqual(len(resp.results), 1)
        self.mock_store.find_player_by_email.assert_not_called()

    def test_origin_zip_is_normalized(self):
        resp = self.search(radius_miles=10, origin_zip="20147-1234")
        self.assertEqual(resp.origin_zip, "20147")

    def test_an_unknown_typed_zip_is_a_400(self):
        with self.assertRaises(HTTPException) as ctx:
            self.search(radius_miles=10, origin_zip="00000")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["code"], "origin_zip_unknown")

    def test_a_malformed_typed_zip_is_a_400(self):
        with self.assertRaises(HTTPException) as ctx:
            self.search(radius_miles=10, origin_zip="abc")
        self.assertEqual(ctx.exception.detail["code"], "origin_zip_unknown")

    def test_no_zip_anywhere_is_a_400_telling_the_player_what_to_do(self):
        self.mock_store.find_player_by_email.return_value = player(SEARCHER, zip_code=None)
        with self.assertRaises(HTTPException) as ctx:
            self.search(radius_miles=25)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["code"], "origin_zip_missing")
        self.assertIn("profile", ctx.exception.detail["message"])

    def test_an_unplaceable_profile_zip_is_treated_as_missing(self):
        self.mock_store.find_player_by_email.return_value = player(SEARCHER, zip_code="00000")
        with self.assertRaises(HTTPException) as ctx:
            self.search(radius_miles=25)
        self.assertEqual(ctx.exception.detail["code"], "origin_zip_missing")

    def test_a_vanished_searcher_is_a_404(self):
        self.mock_store.find_player_by_email.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            self.search(radius_miles=25)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_the_origin_is_not_looked_up_when_no_radius_is_requested(self):
        self.search(first_name="b")
        self.mock_store.find_player_by_email.assert_not_called()


class TestLimit(PlayerSearchTestCase):
    def test_limit_truncates_and_count_reflects_what_was_returned(self):
        self.mock_store.find_players.return_value = [
            player(f"p{i}@x.com", last=f"Name{i:02d}") for i in range(10)]
        resp = self.search(first_name="p", limit=3)
        self.assertEqual(len(resp.results), 3)
        self.assertEqual(resp.count, 3)

    def test_truncation_happens_after_sorting_so_the_nearest_survive(self):
        self.mock_store.find_players.return_value = [
            player("rva@x.com", zip_code="23219"),      # ~103 mi
            player("sterling@x.com", zip_code="20164"), # ~4 mi
        ]
        resp = self.search(radius_miles=200, limit=1)
        self.assertEqual([r.email for r in resp.results], ["sterling@x.com"])


if __name__ == "__main__":
    unittest.main()
