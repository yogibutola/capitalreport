import unittest
from importlib.util import find_spec

from app.utils.geo import coordinates_for_zip, zip_is_known

HAS_ZIPCODES = find_spec("zipcodes") is not None


@unittest.skipUnless(HAS_ZIPCODES, "the 'zipcodes' package is not installed")
class TestRealZipDataset(unittest.TestCase):
    """Smoke test against the actual dataset.

    Everything else about geo.py is tested with the data source patched out, so
    this is the only thing that would notice `zipcodes` changing its API or
    dropping the lat/long keys. Skipped rather than failed on a bare checkout.
    """

    def setUp(self):
        coordinates_for_zip.cache_clear()

    def test_a_real_zip_resolves_to_the_right_place(self):
        coords = coordinates_for_zip("20147")  # Ashburn, VA
        self.assertIsNotNone(coords)
        self.assertAlmostEqual(coords.lat, 39.04, delta=0.2)
        self.assertAlmostEqual(coords.lon, -77.48, delta=0.2)

    def test_zip_plus_four_resolves_the_same_as_its_five_digit_prefix(self):
        self.assertEqual(coordinates_for_zip("20147-1234"), coordinates_for_zip("20147"))

    def test_a_non_existent_zip_is_unknown(self):
        self.assertFalse(zip_is_known("00000"))


if __name__ == "__main__":
    unittest.main()
