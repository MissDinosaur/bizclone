import hashlib
import hmac
import os

from fastapi import HTTPException, Request

DISABLE_SIGNATURE = os.getenv("DISABLE_META_SIGNATURE", "0") == "1"
APP_SECRET = os.getenv("META_APP_SECRET") or os.getenv("FACEBOOK_APP_SECRET")


def verify_meta_signature(request: Request, body_bytes: bytes) -> None:
    """
    Verify Meta webhook signature from the X-Hub-Signature-256 header.
    Signature verification can be disabled locally with DISABLE_META_SIGNATURE=1.
    """
    if DISABLE_SIGNATURE:
        return

    if not APP_SECRET:
        raise HTTPException(status_code=500, detail="Missing Facebook app secret")

    header = request.headers.get("X-Hub-Signature-256", "")
    if not header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Missing signature")

    received_sig = header.split("sha256=", 1)[1].strip()
    expected = hmac.new(APP_SECRET.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(received_sig, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")