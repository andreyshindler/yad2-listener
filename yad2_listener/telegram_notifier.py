"""Send messages through the Telegram Bot API."""

from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, *, session: requests.Session | None = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._session = session or requests.Session()

    @property
    def _base_url(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}"

    def send(self, text: str, *, disable_preview: bool = False, timeout: int = 20) -> bool:
        """Send a text message. Returns True on success."""
        try:
            response = self._session.post(
                f"{self._base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "disable_web_page_preview": disable_preview,
                },
                timeout=timeout,
            )
            response.raise_for_status()
            return True
        except requests.RequestException as exc:
            log.error("Failed to send Telegram message: %s", exc)
            return False
