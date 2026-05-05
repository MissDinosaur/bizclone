"""
Recording downloader for fetching audio from external sources.
"""
import httpx
from typing import Optional, Tuple
from pathlib import Path

from app.config.settings import settings
from app.core.logging import get_logger
from app.core.exceptions import RecordingDownloadError

logger = get_logger(__name__)


class RecordingDownloader:
    """Downloads recordings from external sources."""

    def __init__(self):
        """Initialize recording downloader."""
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    async def download_from_url(
        self,
        url: str,
        call_sid: str,
        auth: Optional[Tuple[str, str]] = None
    ) -> Tuple[bytes, str]:
        """
        Download recording from any URL.

        Args:
            url: URL of the recording
            call_sid: Call session ID
            auth: Optional tuple of (username, password) for authentication

        Returns:
            Tuple of (audio_content, content_type)

        Raises:
            RecordingDownloadError: If download fails
        """
        try:
            logger.info(
                "downloading_recording_from_url",
                call_sid=call_sid,
                url=url
            )

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, auth=auth)
                response.raise_for_status()

                content = response.content
                content_type = response.headers.get('content-type', 'audio/wav')

                logger.info(
                    "recording_downloaded_from_url",
                    call_sid=call_sid,
                    size_bytes=len(content),
                    content_type=content_type
                )

                return content, content_type

        except Exception as exc:
            logger.error(
                "url_download_error",
                call_sid=call_sid,
                url=url,
                error=str(exc),
                exc_info=True
            )
            raise RecordingDownloadError(f"Failed to download recording from URL: {str(exc)}")

