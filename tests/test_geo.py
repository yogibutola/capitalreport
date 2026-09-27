import unittest
from unittest.mock import patch

from app.utils import geo
from app.utils.geo import (
    Coordinates,
    InvalidZipError,
    coordinates_for_zip,
    distance_miles,
    miles_between_zips,
    normalize_zip,
    zip_is_known,
)


def record(lat, lon):
    """A dataset row. Note lat/long are STRINGS, as the real package returns."""
    return {"lat": str(lat), "long": str(lon), "city": "Somewhere", "state": "VA"}


class TestNormalizeZip(unittest.TestCase):
    def test_accepts_plain_five_digits(self):
        self.assertEqual(normalize_zip("20147"), "20147")

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(normalize_zip("  20147  "), "20147")

    def test_truncates_zip_plus_four(self):
        self.assertEqual(normalize_zip("20147-1234"), "20147")
        self.assertEqual(normalize_zip("20147 1234"), "20147")

    def test_blank_input_is_not_set_rather_than_an_error(self):
        """The profile form sends '' (not null) when a field is cleared, so blank
        has to mean "no ZIP" or clearing it would be impossible."""
        for blank in (None, "", "   "):
            self.assertIsNone(normalize_zip(blank))

    def test_rejects_wrong_length_and_non_numeric(self):
        for bad in ("2014", "201471", "abcde", "20147-12"):
            with self.assertRaises(InvalidZipError):
                normalize_zip(bad)


class TestCoordinatesForZip(unittest.TestCase):
    def setUp(self):
        # coordinates_for_zip is lru_cached; without this, fixtures leak between tests.
        coordinates_for_zip.cache_clear()

    def test_string_lat_long_become_floats(self):
        with patch.object(geo, '_zip_record', return_value=record("39.0373", "-77.4805")):
            coords = coordinates_for_zip("20147")
        self.assertEqual(coords, Coordinates(lat=39.0373, lon=-77.4805))

    def test_unknown_zip_is_none(self):
        with patch.object(geo, '_zip_record', return_value=None):
            self.assertIsNone(coordinates_for_zip("00000"))

    def test_unparseable_zip_is_none_rather_than_raising(self):
        """The degradation contract: only normalize_zip raises, never this."""
        with patch.object(geo, '_zip_record') as seam:
            self.assertIsNone(coordinates_for_zip("nonsense"))
        seam.assert_not_called()

    def test_blank_zip_is_none(self):
        with patch.object(geo, '_zip_record') as seam:
            self.assertIsNone(coordinates_for_zip(None))
            self.assertIsNone(coordinates_for_zip(""))
        seam.assert_not_called()

    def test_garbage_coordinates_in_the_record_are_none(self):
        for bad in ({"lat": "north", "long": "-77.48"}, {"long": "-77.48"}, {"lat": None, "long": None}):
            coordinates_for_zip.cache_clear()
            with patch.object(geo, '_zip_record', return_value=bad):
                self.assertIsNone(coordinates_for_zip("20147"))

    def test_result_is_cached(self):
        with patch.object(geo, '_zip_record', return_value=record(39.0, -77.0)) as seam:
            coordinates_for_zip("20147")
            coordinates_for_zip("20147")
        seam.assert_called_once_with("20147")

    def test_zip_is_known(self):
        with patch.object(geo, '_zip_record', return_value=record(39.0, -77.0)):
            self.assertTrue(zip_is_known("20147"))
        coordinates_for_zip.cache_clear()
        with patch.object(geo, '_zip_record', return_value=None):
            self.assertFalse(zip_is_known("00000"))
        self.assertFalse(zip_is_known(None))


class TestZipRecordDegradation(unittest.TestCase):
    def setUp(self):
        coordinates_for_zip.cache_clear()
        geo._warned_missing_package = False

    def tearDown(self):
        geo._warned_missing_package = False

    def test_missing_package_returns_none_instead_of_raising(self):
        """An image built without `zipcodes` must degrade to "no results", not 500."""
        real_import = __builtins__['__import__'] if isinstance(__builtins__, dict) else __builtins__.__import__

        def fail_on_zipcodes(name, *args, **kwargs):
            if name == 'zipcodes':
                raise ImportError("No module named 'zipcodes'")
            return real_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=fail_on_zipcodes):
            self.assertIsNone(geo._zip_record("20147"))

    def test_value_error_from_the_dataset_is_swallowed(self):
        """The package raises ValueError for input under 5 chars."""
        fake = unittest.mock.MagicMock()
        fake.matching.side_effect = ValueError("Invalid format")
        with patch.dict('sys.modules', {'zipcodes': fake}):
            self.assertIsNone(geo._zip_record("2014"))

    def test_empty_match_list_is_none(self):
        fake = unittest.mock.MagicMock()
        fake.matching.return_value = []
        with patch.dict('sys.modules', {'zipcodes': fake}):
            self.assertIsNone(geo._zip_record("00000"))


class TestDistanceMiles(unittest.TestCase):
    def test_identical_points_are_zero(self):
        p = Coordinates(39.0373, -77.4805)
        self.assertAlmostEqual(distance_miles(p, p), 0.0, places=6)

    def test_one_degree_of_latitude_is_about_69_miles(self):
        a = Coordinates(39.0, -77.0)
        b = Coordinates(40.0, -77.0)
        self.assertAlmostEqual(distance_miles(a, b), 69.1, delta=0.7)

    def test_is_symmetric(self):
        a = Coordinates(39.0373, -77.4805)
        b = Coordinates(38.9072, -77.0369)
        self.assertAlmostEqual(distance_miles(a, b), distance_miles(b, a), places=9)

    def test_known_city_pair(self):
        # Ashburn VA -> Washington DC is roughly 26 miles as the crow flies.
        ashburn = Coordinates(39.0373, -77.4805)
        dc = Coordinates(38.9072, -77.0369)
        self.assertAlmostEqual(distance_miles(ashburn, dc), 26.0, delta=2.0)


class TestMilesBetweenZips(unittest.TestCase):
    def setUp(self):
        coordinates_for_zip.cache_clear()

    def test_none_when_either_side_cannot_be_placed(self):
        with patch.object(geo, '_zip_record', side_effect=[record(39.0, -77.0), None]):
            self.assertIsNone(miles_between_zips("20147", "00000"))

    def test_distance_when_both_resolve(self):
        with patch.object(geo, '_zip_record', side_effect=[record(39.0, -77.0), record(40.0, -77.0)]):
            self.assertAlmostEqual(miles_between_zips("20147", "20148"), 69.1, delta=0.7)


if __name__ == "__main__":
    unittest.main()
