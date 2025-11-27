from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

load_dotenv()


class Recipe(BaseModel):
    recipe_name: str
    ingredients: list[str]


client = genai.Client()

grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)

instructions = "Format the json response properly so that it can be easily understandable."
query = "List a few popular cookie recipes, and include the amounts of ingredients."
response = client.models.generate_content(
    model="gemini-2.5-flash",
    config=types.GenerateContentConfig(
        temperature=0,
        # tools=[grounding_tool],
        system_instruction=instructions,
        response_mime_type="application/json",
        response_schema=list[Recipe]
    ),
    contents=query
)

# Use the response as a JSON string.
# print(response.text)

# Use instantiated objects.
my_recipes: list[Recipe] = response.parsed

for recipe in my_recipes:
    print(recipe)