"""The polling loop that ties fetching, dedup, and notification together."""

from __future__ import annotations

import logging
import time

import requests

from .config import Config
from .state import SeenStore
from .telegram_notifier import TelegramNotifier
from .yad2_client import Listing, Yad2FetchError, fetch_listings

log = logging.getLogger(__name__)


class Yad2Listener:
    def __init__(self, config: Config):
        self.config = config
        self.store = SeenStore(config.state_file)
        self.notifier = TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id)
        self.session = requests.Session()

    def find_new(self, listings: list[Listing]) -> list[Listing]:
        """Return listings not previously seen, and mark them as seen."""
        new = [item for item in listings if item.id not in self.store]
        for item in new:
            self.store.add(item.id)
        return new

    def poll_once(self, *, notify: bool = True) -> list[Listing]:
        """One fetch → dedup → notify cycle. Returns the new listings."""
        listings = fetch_listings(self.config.search_url, session=self.session)
        log.info("Fetched %d listings", len(listings))

        new = self.find_new(listings)
        if new:
            log.info("Found %d new listing(s)", len(new))
            if notify:
                for item in new:
                    self.notifier.send("🆕 מודעה חדשה ביד2\n\n" + item.summary())
        self.store.save()
        return new

    def run(self) -> None:
        """Poll forever. The very first cycle only records the baseline so we
        don't spam every existing listing on startup."""
        log.info(
            "Starting Yad2 listener (interval=%ss, %d ids already known)",
            self.config.poll_interval,
            len(self.store),
        )

        first_run = len(self.store) == 0
        while True:
            try:
                new = self.poll_once(notify=not first_run)
                if first_run:
                    log.info("Baseline established with %d listings; no alerts sent", len(new))
                    first_run = False
            except Yad2FetchError as exc:
                log.warning("Fetch failed, will retry next cycle: %s", exc)
            except requests.RequestException as exc:
                log.warning("Fetch failed, will retry next cycle: %s", exc)
            except Exception:  # keep the loop alive on unexpected errors
                log.exception("Unexpected error during poll")

            time.sleep(self.config.poll_interval)
