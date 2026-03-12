import logging
from rag.retriever import KnowledgeRetriever
from llm_engine.llm_client import LLMClient
from knowledge_base.email_history_store import EmailHistoryStore
import config.config as cfg

logger = logging.getLogger(__name__)


class EmailRAGPipeline:
    """
    Full Retrieval-Augmented Generation pipeline with email history context:

    Email → Retrieve KB Context → Retrieve Email History → Prompt → LLM Reply Draft
    """

    def __init__(self):
        self.retriever = KnowledgeRetriever()
        self.llm = LLMClient()
        self.email_store = EmailHistoryStore()

    def generate_email_reply(self, customer_email: str, intent: str, booking=None):
        """
        Generate an email reply draft using:

        - customer email text
        - predicted intent
        - retrieved business knowledge
        - email conversation history (previous interactions)
        - optional booking info
        """

        # -----------------------------
        # Step 1: Retrieve KB context
        # -----------------------------
        retrieved_docs = self.retriever.retrieve(customer_email)
        context = "\n".join([f"- {doc}" for doc in retrieved_docs])

        # -----------------------------
        # Step 2: Retrieve email history
        #Include previous conversations for context
        # -----------------------------
        history_context = self.email_store.get_conversation_for_prompt(
            customer_email,
            limit=5  # Last 5 interactions
        )
        logger.debug(f"Retrieved email history for {customer_email}")

        # -----------------------------
        # Step 3: Add scheduling context
        # -----------------------------
        booking_text = ""
        if booking:
            booking_text = f"\nAppointment booked: {booking}"

        # -----------------------------
        # Step 4: Build LLM prompt with history context
        # -----------------------------
        prompt = f"""
You are BizClone, an AI email assistant for a {cfg.BUSINESS_DOMAIN} business.

CONVERSATION HISTORY:
{history_context}

---

CURRENT EMAIL:
\"\"\"{customer_email}\"\"\"

Detected intent: {intent}

RELEVANT BUSINESS KNOWLEDGE:
{context}

{booking_text}

TASK:
Write a professional, friendly email reply.
- Use the business owner's tone and style from previous interactions if applicable
- Reference previous conversations if relevant to provide continuity
- Be concise and accurate
- Address the customer's current concern
- Do NOT include signature
- Do NOT include company name
- Do NOT include placeholders
- Only write the email body
"""

        # -----------------------------
        # Step 5: Generate reply via LLM
        # -----------------------------
        reply = self.llm.generate(prompt) + "\n\n" + cfg.COMPANY_SIGNATURE
        logger.debug(f"Generated reply for {customer_email} (intent: {intent})")
        
        return reply, retrieved_docs
