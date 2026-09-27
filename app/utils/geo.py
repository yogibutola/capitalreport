"""ZIP-code geocoding and great-circle distance.

The app stores a player's location as a US ZIP code (plus free-text city/state
for display). This module turns that ZIP into coordinates so "players within 25
miles of me" can be answered, and is the only place that knows where the
coordinate data comes from.

Degradation contract, so callers stay trivial: ``coordinates_for_zip`` NEVER
raises. An unknown ZIP, an unparseable one, garbage stored in Mongo, or a
missing ``zipcodes`` package all return ``None``, and the caller drops that
player from distance-filtered results. Only ``normalize_zip`` raises, and only
at a write boundary (signup / profile save) where a human can fix the input.

Swapping the data source means rewriting ``_zip_record`` and nothing else.
"""

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from math import asin, cos, radians, sin, sqrt
from typing import Optional

logger = logging.getLogger(__name__)

# Mean Earth radius in miles (IUGG), the usual choice for haversine.
EARTH_RADIUS_MILES = 3958.7613

_DIGITS = re.compile(r"\D")

# The `zipcodes` package is an optional-at-runtime concern: if the image was
# built without it, distance search degrades to "no results" rather than 500s.
# We only want to say so once, not per request.
_warned_missing_package = False


class InvalidZipError(ValueError):
    """Raised when a caller-supplied ZIP code isn't a usable US ZIP."""


@dataclass(frozen=True)
class Coordinates:
    lat: float
    lon: float


def normalize_zip(raw: Optional[str]) -> Optional[str]:
    """Reduce user input to a bare 5-digit ZIP, or ``None`` when it's blank.

    Accepts ``"20147"``, ``" 20147 "``, ``"20147-1234"`` and ``"20147 1234"``.
    Blank input (including the empty string the profile form sends when a field
    is cleared) is ``None`` rather than an error.

    Raises:
        InvalidZipError: input is present but not a 5- or 9-digit US ZIP.
    """
    if raw is None:
        return None

    text = str(raw).strip()
    if not text:
        return None

    digits = _DIGITS.sub("", text)
    if len(digits) not in (5, 9):
        raise InvalidZipError("Enter a 5-digit US ZIP code")

    return digits[:5]


def _zip_record(zip5: str) -> Optional[dict]:
    """Look one ZIP up in the dataset. The single seam over the data source.

    Imports ``zipcodes`` lazily: the dataset decompresses on first query
    (~200ms), so keeping the import in here leaves app startup and pytest
    collection untouched.
    """
    global _warned_missing_package

    try:
        import zipcodes
    except ImportError:
        if not _warned_missing_package:
            _warned_missing_package = True
            logger.warning(
                "The 'zipcodes' package is not installed, so distance search will "
                "return no results. Regenerate requirements.txt and rebuild the image."
            )
        return None

    try:
        # Raises for input under 5 characters, returns [] for a well-formed but
        # unknown ZIP. Both mean "we can't place this player".
        matches = zipcodes.matching(zip5)
    except (ValueError, TypeError):
        return None

    return matches[0] if matches else None


@lru_cache(maxsize=8192)
def coordinates_for_zip(zip_code: Optional[str]) -> Optional[Coordinates]:
    """Coordinates for a ZIP, or ``None`` if it can't be placed. Never raises.

    Cached because a roster search geocodes every candidate and players cluster
    into a handful of ZIPs — which is also why we don't denormalise coordinates
    onto the player document. Tests that patch ``_zip_record`` must call
    ``coordinates_for_zip.cache_clear()`` or fixtures leak between cases.
    """
    try:
        zip5 = normalize_zip(zip_code)
    except InvalidZipError:
        return None

    if zip5 is None:
        return None

    record = _zip_record(zip5)
    if not record:
        return None

    try:
        # The dataset carries lat/long as strings ('39.0373').
        return Coordinates(lat=float(record["lat"]), lon=float(record["long"]))
    except (KeyError, TypeError, ValueError):
        return None


def zip_is_known(zip_code: Optional[str]) -> bool:
    """True when this ZIP can be placed on the map. Blank input is not "known"."""
    return coordinates_for_zip(zip_code) is not None


def distance_miles(a: Coordinates, b: Coordinates) -> float:
    """Great-circle distance in miles between two points (haversine)."""
    lat1, lon1 = radians(a.lat), radians(a.lon)
    lat2, lon2 = radians(b.lat), radians(b.lon)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * asin(sqrt(h))


def miles_between_zips(a: Optional[str], b: Optional[str]) -> Optional[float]:
    """Distance between two ZIPs, or ``None`` if either can't be placed."""
    coords_a = coordinates_for_zip(a)
    coords_b = coordinates_for_zip(b)
    if coords_a is None or coords_b is None:
        return None
    return distance_miles(coords_a, coords_b)
