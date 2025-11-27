import uuid

from dotenv import load_dotenv
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent import root_agent

load_dotenv()

inmemorySessionService = InMemorySessionService()
initial_sate = {
    "user_name": "Yogi Butola",
    "user_preferences": """
    I like to play pickelball, table tennis and pool.
    My favorite food is Indian and Mediterranian.
    Loves to be with friends and learn new skills.
    """
}
APP_NAME = "BUTOLA_BOT"
USER_ID = "ybutola"
SESSION_ID = str(uuid.uuid4())
session = inmemorySessionService.create_session(
    app_name=APP_NAME,
    user_id=USER_ID,
    session_id=SESSION_ID,
    state=initial_sate
)

runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=inmemorySessionService
)
query_1 = "What is Yogi's favorite food?"
query_2 = "What does Yogi's likes to play?"
message = types.Content(
    role="user", parts=[types.Part(text=query_2)]
)

for event in runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=message):
    if event.is_final_response():
        final_response = event.content.parts[0].text
        print("Agent Response: ", final_response)


print ("=== session event exploration ===")
session = inmemorySessionService.get_session(app_name=APP_NAME, user_id= USER_ID, session_id=SESSION_ID)
print("Session ID:", session.id)
print("User ID:", session.user_id)
print("Events:", session.events)