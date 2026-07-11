import logging
import os
import random

from dotenv import load_dotenv
from google.cloud import aiplatform
from vertexai.generative_models import GenerationConfig, GenerativeModel

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "stable-smithy-270416")
REGION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
GENERATION_MODEL = "gemini-2.5-flash"

# A few angles to nudge the model toward a different quote on every call.
_THEMES = [
    "the joy of the third-shot drop",
    "dinking patience at the kitchen line",
    "friendly rivalry and good sportsmanship",
    "staying out of the non-volley zone",
    "the addictive sound of the pickleball pop",
    "teamwork with your doubles partner",
    "chasing that perfect ATP shot",
    "never giving up on a dying quail",
    "the community and friendships at the courts",
    "resetting after a tough point",
]

_FALLBACK = "Dink today, dominate tomorrow — the kitchen is calling."


class PBQuoteService:
    """Generates a short, fresh, AI-written pickleball quote for the header.

    Uses Vertex AI (matching the app's other AI agents) so it authenticates via
    the service account / ADC rather than a Gemini Developer API key.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        aiplatform.init(project=PROJECT_ID, location=REGION)
        self.model = GenerativeModel(GENERATION_MODEL)

    def generate_quote(self) -> str:
        theme = random.choice(_THEMES)
        prompt = (
            "Write a single short, original, uplifting pickleball quote "
            f"inspired by {theme}. Keep it under 18 words. Make it witty or "
            "motivational. Return only the quote text on one line with no "
            "surrounding quotation marks, author name, or extra commentary."
        )
        try:
            response = self.model.generate_content(
                contents=prompt,
                # High temperature keeps every login fresh; the token budget is
                # generous so gemini-2.5-flash's thinking step doesn't starve
                # the visible answer.
                generation_config=GenerationConfig(
                    temperature=1.4,
                    max_output_tokens=1024,
                ),
            )
            quote = (response.text or "").strip().strip('"').strip()
            if quote:
                # Collapse any stray newlines into a single-line quote.
                return " ".join(quote.split())
        except Exception as e:  # noqa: BLE001
            self.logger.warning("Failed to generate pickleball quote: %s", e)

        return _FALLBACK
