from rag.retriever import KnowledgeRetriever
from llm_engine.llm_client import LLMClient
import config.config as cfg

class EmailRAGPipeline:
    """
    Full Retrieval-Augmented Generation pipeline:

    Email → Retrieve KB Context → Prompt → LLM Reply Draft
    """

    def __init__(self):
        self.retriever = KnowledgeRetriever()
        self.llm = LLMClient()

    def generate_email_reply(self, customer_email: str, intent: str, booking=None):
        """
        Generate an email reply draft using:

        - customer email text
        - predicted intent
        - retrieved business knowledge
        - optional booking info
        """

        # -----------------------------
        # Step 1: Retrieve KB context
        # -----------------------------
        retrieved_docs = self.retriever.retrieve(customer_email)

        context = "\n".join([f"- {doc}" for doc in retrieved_docs])

        # -----------------------------
        # Step 2: Add scheduling context
        # -----------------------------
        booking_text = ""
        if booking:
            booking_text = f"\nAppointment booked: {booking}"

        # -----------------------------
        # Step 3: Build LLM prompt
        # -----------------------------
        prompt = f"""
You are BizClone, an AI email assistant for a {cfg.BUSINESS_DOMAIN} business.

Customer email:
\"\"\"{customer_email}\"\"\"

Detected intent: {intent}

Relevant business knowledge:
{context}

{booking_text}

Task:
Write a professional, friendly email reply.
Use the business owner's tone.
Be concise and accurate.
Do NOT include signature.
Do NOT include company name.
Do NOT include placeholders.
Only write the email body.
"""

        # -----------------------------
        # Step 4: Generate reply via LLM
        # -----------------------------
        reply = self.llm.generate(prompt) + "\n\n" + cfg.COMPANY_SIGNATURE
        
        return reply, retrieved_docs
