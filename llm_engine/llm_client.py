#class LLMClient:
#    """
#    Mock LLM client for MVP (replace with OpenAI API later).
#    """
#
#    def generate(self, prompt: str) -> str:
#        return (
#            "Thank you for your email. Based on our current pricing, "
#            "emergency plumbing services cost €120/hour. "
#            "Please let us know your preferred time for an appointment."
#        )

from openai import OpenAI
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        # Log key availability (don't log the actual key)
        logger.debug(f"OpenAI API Key found: {'*' * 10}...{api_key[-10:] if len(api_key) > 10 else api_key}")

        self.client = OpenAI(api_key=api_key)

    def generate(self, prompt: str):
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are BizClone Email Agent. Write professional, polite, concise replies."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3
            )

            return response.choices[0].message.content
        except Exception as e:
            print("LLM Error:", e)
            return "Thank you for your email. We will respond shortly."