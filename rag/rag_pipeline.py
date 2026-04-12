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

    def generate_email_reply(self, customer_email: str, body: str, intent: str, booking=None):
        """
        Generate an email reply draft using:
        - customer email address
        - body of the email
        - predicted intent
        - retrieved business knowledge
        - email conversation history (previous interactions)
        - optional booking info
        """

        # -----------------------------
        # Step 1: Retrieve KB context
        # -----------------------------
        retrieved_docs = self.retriever.retrieve(body)
        context = "\n".join([f"- {doc}" for doc in retrieved_docs])

        # -----------------------------
        # Step 2: Retrieve email history
        #Include previous conversations for context
        # -----------------------------
        history_context = self.email_store.get_conversation_for_prompt(
            customer_email,
            limit=5  # Last 5 interactions
        )
        logger.debug(f"Retrieved last 5 email history for {customer_email}")

        # -----------------------------
        # Step 3: Add scheduling context
        # -----------------------------
        booking_text = ""
        if booking and booking.get('slot'):
            # CRITICAL: Include the exact appointment time that LLM MUST use in the reply
            appointment_slot = booking.get('slot')
            # Parse slot to human-readable format for LLM
            from datetime import datetime
            try:
                slot_dt = datetime.fromisoformat(appointment_slot)
                readable_time = slot_dt.strftime("%B %d at %I:%M %p")  # e.g., "April 10 at 2:00 PM"
            except:
                readable_time = appointment_slot
            
            booking_text = f"""
CRITICAL - Appointment Time:
The customer's appointment has been scheduled for: {appointment_slot}
You MUST include this EXACT appointment time in your email reply.
Use this format in the email: "{readable_time}" (or "{appointment_slot}")
DO NOT use any other date/time in the reply - this is the ONLY confirmed appointment date/time."""

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
IMPORTANT INSTRUCTIONS:
- Only write the email body (plain text, no HTML)
- Do NOT include "Subject:" line or any subject text in your reply
- Do NOT include signature
- Do NOT include company name
- Do NOT include placeholders or template variables
- Do NOT include any headers like From, To, Date
- Use the business owner's tone and style from previous interactions if applicable
- Reference previous conversations if relevant to provide continuity
- Be concise and accurate
- Address the customer's current concern
"""

        # -----------------------------
        # Step 5: Generate reply via LLM
        # -----------------------------
        reply = self.llm.generate(prompt) + "\n\n" + cfg.COMPANY_SIGNATURE
        
        # Clean up: Remove "Subject:" line if LLM included it (despite instructions)
        # Email Subject should be set in headers, not in body
        # lines = reply.split('\n')
        # cleaned_lines = []
        # for line in lines:
        #     # Skip lines that start with "Subject:" (case-insensitive)
        #     if not line.strip().lower().startswith('subject:'):
        #         cleaned_lines.append(line)
        # reply = '\n'.join(cleaned_lines).strip()
        
        logger.debug(f"Generated reply for {customer_email} (intent: {intent})")
        
        return reply, retrieved_docs
