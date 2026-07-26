"""Runtime configuration, loaded from environment variables / a .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv is optional at runtime
    def load_dotenv(*_args, **_kwargs):
        return False


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    telegram_chat_id: str
    search_url: str
    poll_interval: int
    state_file: str

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()

        missing = [
            name
            for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "YAD2_SEARCH_URL")
            if not os.environ.get(name)
        ]
        if missing:
            raise SystemExit(
                "Missing required environment variables: "
                + ", ".join(missing)
                + ".\nCopy .env.example to .env and fill it in."
            )

        return cls(
            telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
            telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
            search_url=os.environ["YAD2_SEARCH_URL"],
            poll_interval=int(os.environ.get("POLL_INTERVAL", "300")),
            state_file=os.environ.get("STATE_FILE", "state.json"),
        )
