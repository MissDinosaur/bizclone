import json
import logging
import os
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from channels.facebook.facebook_agent import FacebookAgent
from channels.facebook.facebook_client import FacebookClient
from channels.facebook.security import verify_meta_signature
from channels.schemas import NormalizedMessage
from database.initialization import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["facebook"])

VERIFY_TOKEN = (
    os.getenv("META_VERIFY_TOKEN")
    or os.getenv("FACEBOOK_VERIFY_TOKEN")
    or "bizclone_verify_123"
)


def _conversation_id(sender_id: str, recipient_id: str) -> str:
    return f"fb:{recipient_id}:{sender_id}"


def _extract_text_messages(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    extracted_messages: List[Dict[str, Any]] = []

    if payload.get("object") != "page":
        return extracted_messages

    for entry in payload.get("entry", []):
        for messaging in entry.get("messaging", []):
            message = messaging.get("message")
            if not message:
                continue

            if message.get("is_echo"):
                continue

            text = (message.get("text") or "").strip()
            if not text:
                continue

            sender_id = str((messaging.get("sender") or {}).get("id") or "")
            recipient_id = str((messaging.get("recipient") or {}).get("id") or "")
            timestamp_ms = messaging.get("timestamp")
            mid = str(message.get("mid") or "")

            if not sender_id or not recipient_id or timestamp_ms is None or not mid:
                continue

            extracted_messages.append(
                {
                    "sender_id": sender_id,
                    "recipient_id": recipient_id,
                    "text": text,
                    "timestamp_ms": int(timestamp_ms),
                    "mid": mid,
                }
            )

    return extracted_messages


@router.get("/webhook/facebook")
@router.get("/webhook")
async def verify_webhook(request: Request) -> PlainTextResponse:
    q = request.query_params

    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(q.get("hub.challenge") or "", status_code=200)

    return PlainTextResponse("Verification failed", status_code=403)


@router.post("/webhook/facebook")
@router.post("/webhook")
async def receive_webhook(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    body = await request.body()
    verify_meta_signature(request, body)

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    extracted_messages = _extract_text_messages(payload)
    if not extracted_messages:
        return {"ok": True, "messages_count": 0, "replies_sent": 0}

    agent = FacebookAgent()
    facebook_client = FacebookClient()

    processed_count = 0
    replies_sent = 0

    for item in extracted_messages:
        normalized = NormalizedMessage(
            channel="facebook_messenger",
            channel_message_id=item["mid"],
            conversation_id=_conversation_id(item["sender_id"], item["recipient_id"]),
            sender_id=item["sender_id"],
            recipient_id=item["recipient_id"],
            text=item["text"],
            timestamp_ms=item["timestamp_ms"],
            raw=payload,
        )

        result = await agent.handle_incoming(normalized, db)
        processed_count += 1

        reply_text = result.reply.strip() if result.reply else ""
        if not reply_text:
            continue

        logger.info("[FACEBOOK] Reply text: %s", reply_text)

        if normalized.sender_id.startswith("USER_"):
            logger.info("[FACEBOOK] Skipping send_text for local test user")
            continue

        try:
            await facebook_client.send_text(
                recipient_psid=normalized.sender_id,
                text=reply_text,
            )
            replies_sent += 1
        except Exception as exc:
            logger.exception("[FACEBOOK] Failed to send message: %s", exc)

    return {
        "ok": True,
        "messages_count": processed_count,
        "replies_sent": replies_sent,
    }