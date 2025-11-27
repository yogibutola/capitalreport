from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel
import httpx

load_dotenv()


class Recipe(BaseModel):
    recipe_name: str
    ingredients: list[str]


client = genai.Client()
doc_url = "https://discovery.ucl.ac.uk/id/eprint/10089234/1/343019_3_art_0_py4t4l_convrt.pdf"
doc_data = httpx.get(doc_url).content

grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)

instructions = "Format the json response properly so that it can be easily understandable."
query = "Summarize this document"
response = client.models.generate_content(
    model="gemini-2.5-flash",
    config=types.GenerateContentConfig(
        temperature=0,
        # tools=[grounding_tool],
        # system_instruction=instructions,
        # response_schema=list[Recipe]
    ),
    contents=[
        types.Part.from_bytes(data=doc_data, mime_type="application/pdf"),
        query
    ]
)

# Use the response as a JSON string.
print(response.text)
