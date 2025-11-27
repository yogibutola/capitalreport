from google.adk.agents import Agent
from pydantic import BaseModel, Field


class EmailContent(BaseModel):
    subject: str = Field(
        description="The subject line of an email. Should be concise and descriptive"
    )
    body: str = Field(
        "The main content of email.Should be well formatted with proper greeting, paragraphs and signature."
    )


root_agent = Agent(
    model='gemini-2.0-flash-001',
    name='structured_agent',
    description='A helpful assistant for user questions.',
    instruction='You are an agent for writing email. Structure the Email'
                'Greeting: Use the appropriate salutation (“Hi [Name],”, “Dear [Name],”, etc.).'
                'Opening Line: Provide context or acknowledge prior interaction.'
                'Main Body: Clearly explain the message in a logical order (bullet points or paragraphs).'
                'Closing: End with gratitude, a polite remark, or next steps.'
                'Signature: Add sender’s name, title (if relevant), and contact details.',
    output_schema=EmailContent,
    output_key="email"
)
