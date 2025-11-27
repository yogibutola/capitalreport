from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client()

# Define the grounding tool
grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)

instructions = "You are a helpful assistant that answers questions about company's future."
query = "how does the future of Opendoor looks like?"

response = client.models.generate_content(
    model='gemini-2.0-flash-001',
    config=types.GenerateContentConfig(
        temperature=0,
        tools=[grounding_tool],
        system_instruction=instructions),
    contents=query
)

print(response.text)
# print(response.candidates[0].content.parts[0].function_call)


# Streaming
# for chunk in response:
#     print(chunk.text, end="")
