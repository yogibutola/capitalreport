import logging
import re
import unicodedata

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.services.pb_session import issue_session
from app.store.mongo.pb_club_store import PBClubStore
from app.store.mongo.pb_player_store import PBPlayerStore
from app.vo.pb.club import ClubCreate, ClubResponse, ClubSessionResponse, ClubUpdate, VenueCreate, VenueResponse

logger = logging.getLogger(__name__)


def slugify(name: str) -> str:
    """URL-safe club handle: "St. Paul's Paddle Club" -> "st-pauls-paddle-club"."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower().replace("'", "")).strip("-")
    return slug[:60].strip("-") or "club"


class PBClubService:
    def __init__(self, club_store: PBClubStore, player_store: PBPlayerStore):
        self.club_store = club_store
        self.player_store = player_store

    # ---- clubs ---------------------------------------------------------------

    def create_club(self, owner_email: str, req: ClubCreate) -> ClubSessionResponse:
        """Create a club owned by this account and return a session that runs it.

        Raises 409 if the account already runs a club (one club per person).
        """
        owner = self.player_store.find_player_by_email(owner_email)
        if not owner:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        if self.club_store.get_club_by_owner(owner["_id"]):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already run a club")

        doc = {
            "owner_player_id": owner["_id"],
            "name": req.name,
            "slug": self._unique_slug(req.name),
            "contact_email": (req.contact_email or owner["email"]).lower(),
            "phone": req.phone,
            "address": req.address,
        }
        try:
            club = self.club_store.insert_club(doc)
        except DuplicateKeyError as e:
            # Either a parallel request already created this owner's club, or two
            # same-named clubs raced for one slug; the owner case is the one to report.
            if self.club_store.get_club_by_owner(owner["_id"]):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already run a club") from e
            doc["slug"] = self._unique_slug(req.name)
            club = self.club_store.insert_club(doc)

        token, _ = issue_session(owner, club)
        logger.info("Club %s created by %s", club["slug"], owner["email"])
        return ClubSessionResponse(club=self.to_response(club), token=token)

    def create_club_with_owner(self, owner_doc: dict, req: ClubCreate) -> dict:
        """Create a club for an account that was just created (club signup, seeding)."""
        return self.club_store.insert_club({
            "owner_player_id": owner_doc["_id"],
            "name": req.name,
            "slug": self._unique_slug(req.name),
            "contact_email": (req.contact_email or owner_doc["email"]).lower(),
            "phone": req.phone,
            "address": req.address,
        })

    def club_for_owner_email(self, email: str) -> dict | None:
        """The club run by the account with this email, if any (seed scripts, tooling)."""
        owner = self.player_store.find_player_by_email(email)
        return self.club_store.get_club_by_owner(owner["_id"]) if owner else None

    def get_club(self, club_id: str) -> ClubResponse:
        club = self.club_store.get_club(club_id)
        if not club:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")
        return self.to_response(club)

    def update_club(self, club_id: str, req: ClubUpdate) -> ClubResponse:
        fields = req.model_dump(exclude_unset=True)
        if "name" in fields and not fields["name"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Club name cannot be empty")
        if fields.get("contact_email"):
            fields["contact_email"] = fields["contact_email"].lower()
        # The slug is a stable public handle: renaming the club leaves it alone.
        club = self.club_store.update_club(club_id, fields) if fields else self.club_store.get_club(club_id)
        if not club:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")
        return self.to_response(club)

    def _unique_slug(self, name: str) -> str:
        base = slugify(name)
        slug, n = base, 2
        while self.club_store.slug_exists(slug):
            slug, n = f"{base}-{n}", n + 1
        return slug

    @staticmethod
    def to_response(club: dict) -> ClubResponse:
        return ClubResponse(
            id=str(club["_id"]), name=club["name"], slug=club["slug"],
            contact_email=club.get("contact_email"), phone=club.get("phone"), address=club.get("address"),
        )

    # ---- venues ----------------------------------------------------------------

    def list_venues(self, club_id: str) -> list[VenueResponse]:
        return [self._venue_response(v) for v in self.club_store.list_venues(club_id)]

    def add_venue(self, club_id: str, req: VenueCreate) -> VenueResponse:
        return self._venue_response(self.club_store.insert_venue(club_id, req.model_dump()))

    def update_venue(self, club_id: str, venue_id: str, req: VenueCreate) -> VenueResponse:
        venue = self.club_store.update_venue(club_id, venue_id, req.model_dump())
        if not venue:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found")
        return self._venue_response(venue)

    def delete_venue(self, club_id: str, venue_id: str) -> None:
        if not self.club_store.delete_venue(club_id, venue_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found")

    @staticmethod
    def _venue_response(venue: dict) -> VenueResponse:
        return VenueResponse(
            id=str(venue["_id"]), club_id=str(venue["club_id"]), name=venue["name"],
            address=venue.get("address"), zip_code=venue.get("zip_code"), courts=venue.get("courts") or [],
        )
