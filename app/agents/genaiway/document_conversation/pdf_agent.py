import json
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.agents.genaiway.pdfdocument_extraction.investment import Investment

load_dotenv()


class PdfAgent:

    def find_values(self, text: str):
        client = genai.Client()
        # instructions = "You are stock analyst agent, who understands the investment report for an individual account"
        instructions = """
            Format the json response properly so that it can be easily understandable.
        """
        query = """
                Read the document and list the holdings with the following information:
                  Schema = list of objects with fields:
                    - stock_name (string)
                    - quantity (number)
                    - gain_loss (number, float, in USD — no $, no commas, 0 if not applicable))
                """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                temperature=0,
                # tools=[grounding_tool],
                system_instruction=instructions,
                response_schema=list[Investment]
            ),
            contents=[text, query]
        )

        clean_text = re.sub(r"^```json|```$", "", response.text.strip(), flags=re.MULTILINE).strip()
        data = json.loads(clean_text)
        my_investments = [Investment(**item) for item in data]

        # my_investments: list[Investment] = response.parsed
        return my_investments
