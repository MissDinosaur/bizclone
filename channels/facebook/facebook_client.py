import logging
import os

import httpx
from fastapi import HTTPException


logger = logging.getLogger(__name__)


class FacebookClient:
    def __init__(self) -> None:
        graph_api_version = os.getenv("META_GRAPH_API_VERSION") or os.getenv(
            "FACEBOOK_GRAPH_API_VERSION", "v20.0"
        )
        self.page_access_token = os.getenv("META_PAGE_ACCESS_TOKEN") or os.getenv(
            "FACEBOOK_PAGE_ACCESS_TOKEN"
        )
        self.base_url = f"https://graph.facebook.com/{graph_api_version}"

    async def send_text(self, recipient_psid: str, text: str) -> None:
        if not self.page_access_token:
            logger.error("[FACEBOOK CLIENT] Missing Facebook page access token")
            raise HTTPException(status_code=500, detail="Missing Facebook page access token")

        url = f"{self.base_url}/me/messages"
        params = {"access_token": self.page_access_token}
        payload = {
            "messaging_type": "RESPONSE",
            "recipient": {"id": recipient_psid},
            "message": {"text": text},
        }

        logger.info(
            "[FACEBOOK CLIENT] Sending message | recipient=%s | text=%s",
            recipient_psid,
            text,
        )

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(url, params=params, json=payload)

            if response.is_error:
                logger.error(
                    "[FACEBOOK CLIENT] Facebook API error | status=%s | body=%s",
                    response.status_code,
                    response.text,
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Facebook API error: {response.text}",
                )

            logger.info(
                "[FACEBOOK CLIENT] Message sent successfully | response=%s",
                response.text,
            )

        except httpx.TimeoutException as exc:
            logger.exception("[FACEBOOK CLIENT] Request timed out: %s", exc)
            raise HTTPException(status_code=504, detail="Facebook API request timed out") from exc
        except httpx.RequestError as exc:
            logger.exception("[FACEBOOK CLIENT] Network error: %s", exc)
            raise HTTPException(status_code=502, detail="Facebook API network error") from exc