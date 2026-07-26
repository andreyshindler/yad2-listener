"""Entry point: `python main.py` to start monitoring, or with flags to test."""

from __future__ import annotations

import argparse
import logging

from yad2_listener.config import Config
from yad2_listener.listener import Yad2Listener


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor a Yad2 search and alert on new listings via Telegram.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll cycle and exit (useful for testing / cron).",
    )
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="Send a test message to verify Telegram credentials, then exit.",
    )
    args = parser.parse_args()

    _setup_logging()
    config = Config.from_env()
    listener = Yad2Listener(config)

    if args.test_telegram:
        ok = listener.notifier.send("✅ yad2-listener: Telegram is configured correctly.")
        raise SystemExit(0 if ok else 1)

    if args.once:
        new = listener.poll_once()
        logging.info("Done. %d new listing(s).", len(new))
        return

    listener.run()


if __name__ == "__main__":
    main()
