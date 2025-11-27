from google.adk.agents import LlmAgent

root_agent = LlmAgent(
    model='gemini-2.0-flash-001',
    name='session_agent',
    description='A helpful assistant for user questions.',
    instruction="""
        You are a helpful assistant that answers questions about the user's preferences.
        
        Here is some information about the user:
        Name:
        {user_name}
        Preferences:
        {user_preferences}
    """

)
