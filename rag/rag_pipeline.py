import logging
from rag.retriever import KnowledgeRetriever
from llm_engine.llm_client import LLMClient
from channels.email.email_history_store import EmailHistoryStore
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
        # Include previous conversations for context
        # -----------------------------
        history_context = self.email_store.get_conversation_for_prompt(
            customer_email,
            limit=5  # Last 5 interactions
        )
        logger.debug(f"Retrieved last 5 email history for {customer_email}")

        # -----------------------------
        # Step 3: Add scheduling context
        # CRITICAL: Ensure exact appointment time is used in reply
        # Prevent LLM from hallucinating wrong dates/times
        # -----------------------------
        booking_text = ""
        appointed_time_instruction = ""
        if booking and booking.get('slot'):
            appointment_slot = booking.get('slot')
            reasoning = booking.get('reasoning', '')
            
            # Parse slot to human-readable format for LLM
            from datetime import datetime
            try:
                slot_dt = datetime.fromisoformat(appointment_slot)
                readable_time = slot_dt.strftime("%A, %B %d, %Y at %I:%M %p")
                date_short = slot_dt.strftime("%B %d")
                time_short = slot_dt.strftime("%I:%M %p")
            except:
                readable_time = appointment_slot
                date_short = appointment_slot
                time_short = appointment_slot
            
            booking_text = f"""
------------ CONFIRMED APPOINTMENT INFORMATION -----------
APPOINTMENT CONFIRMED FOR: {readable_time}
Alternative formats you can use:
  - "{date_short} at {time_short}"
  - "{appointment_slot}"

CRITICAL - DO NOT DEVIATE FROM THIS TIME:
✗ DO NOT mention any other dates or times
✗ DO NOT suggest alternative times (this is the CONFIRMED time)
✗ DO NOT include uncertain language about this time
✓ DO mention this exact appointment in your reply
✓ DO confirm the customer will receive a calendar invitation
✓ DO include instructions if customer needs to reschedule

Selection reasoning: {reasoning}
"""

            appointed_time_instruction = f"""
**STRICT INSTRUCTION FOR APPOINTMENT BOOKING:**
The appointment is CONFIRMED for {readable_time}.
Your reply MUST confirm this exact date and time using one of these formats ONLY:
  - {readable_time}
  - {date_short} at {time_short}
Do not generate, suggest, or mention any other dates or times."""

        # -----------------------------
        # Step 4: Build LLM prompt with history context
        # Appointment information is placed at the top with high priority
        # -----------------------------
        prompt = f"""
You are BizClone, an AI email assistant for a {cfg.BUSINESS_DOMAIN} business.

{booking_text}

CONVERSATION HISTORY:
{history_context}

---

CURRENT EMAIL FROM CUSTOMER:
\"\"\"{customer_email}\"\"\"

Detected intent: {intent}

RELEVANT BUSINESS KNOWLEDGE:
{context}

{appointed_time_instruction}

TASK:
Write a professional, friendly email reply that confirms the appointment and addresses customer's needs.

CRITICAL REQUIREMENTS FOR APPOINTMENT BOOKINGS:
1. Always explicitly state the appointment date and time
2. Use ONLY the exact date/time provided above
3. Confirm customer will receive calendar invitation (ICS file)
4. Keep reply concise (3-5 sentences)

OUTPUT REQUIREMENTS:
- Only write the email body (plain text, no HTML)
- Do NOT include "Subject:" line
- Do NOT include signature (will be added automatically)
- Do NOT include company name or sender information
- Do NOT include placeholders or {{variables}}
- Do NOT include any headers like From, To, Date
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
