from google.adk.agents import Agent
from google.adk.tools import google_search
from google.genai import types

root_agent = Agent(
    model='gemini-2.0-flash-001',
    name='tool_agent',
    description='A helpful assistant for user questions.',
    instruction='Answer user questions to the best of your knowledge',
    tools=[google_search],
    generate_content_config=types.GenerateContentConfig(
        temperature=0.2,  # More deterministic output
        max_output_tokens=250
    )
)
