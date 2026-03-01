from channels.email.parser import parse_email
from channels.email.intent_classifier import IntentClassifier

from rag.rag_pipeline import EmailRAGPipeline
from scheduling.scheduler import check_availability, book_slot
import config.config as config

""" Email Agent Orchestrator (End-to-End Brain) """

rag = EmailRAGPipeline()
intent_model = IntentClassifier()


def process_email(email_payload: dict):
    """
    End-to-end Email Agent pipeline:

    1. Parse incoming email
    2. Predict intent using NLP model
    3. Retrieve relevant KB context (RAG)
    4. Generate final reply draft using LLM
    5. Optionally handle scheduling requests
    """

    # -----------------------------
    # Step 1: Parse email payload
    # -----------------------------
    parsed = parse_email(email_payload)
    text = parsed["text"]

    # -----------------------------
    # Step 2: Intent Detection (NLP)
    # -----------------------------
    intent_result = intent_model.predict_intent(text)
    intent = intent_result["intent"]
    print(f"This email intent is clasified as: {intent}")
    # -----------------------------
    # Step 3: Scheduling Logic (Optional)
    # -----------------------------
    booking = None
    if intent == config.APPOINTMENT:
        slots = check_availability()
        booking = book_slot(email_payload["from"], slots[0])

    # -----------------------------
    # Step 4: RAG + LLM Email Draft
    # -----------------------------
    reply_text, retrieved_docs = rag.generate_email_reply(customer_email=text, intent=intent, booking=booking)

    # Emergency emails require owner review
    if intent == config.EMERGENCY:
        return {
            "channel": "email",
            "status": "needs_review",
            "intent": intent,
            "reply": reply_text,
            "customer_question": text
        }
    
    return {
        "channel": "email",
        "status": "auto_send",
        "intent": intent,
        "retrieved_docs": retrieved_docs,
        "booking": booking,
        "reply": reply_text
    }
