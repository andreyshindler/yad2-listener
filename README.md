# yad2-listener

Monitor a [Yad2](https://www.yad2.co.il) search and get a **Telegram** message
whenever a new listing shows up — for apartments, cars, second-hand items, or
anything else Yad2 lists.

It polls your search on an interval, remembers which listings it has already
seen (in a small JSON file), and only alerts you about genuinely new ones.

## How it works

1. You give it a normal Yad2 search-page URL (the one in your browser bar).
2. It converts that to Yad2's JSON feed API (`gw.yad2.co.il`) and fetches results.
3. New listing ids (ones not in `state.json`) are sent to your Telegram chat.
4. It sleeps for `POLL_INTERVAL` seconds and repeats.

The first cycle just records a baseline of the currently-live listings so you
don't get flooded with alerts for everything that already exists.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env`:

| Variable | What it is |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Create a bot with [@BotFather](https://t.me/BotFather) and copy the token. |
| `TELEGRAM_CHAT_ID` | Message [@userinfobot](https://t.me/userinfobot) to get your numeric chat id. |
| `YAD2_SEARCH_URL` | Paste your Yad2 search URL, e.g. `https://www.yad2.co.il/realestate/forsale?city=5000&price=0-2000000&rooms=3-4`. |
| `POLL_INTERVAL` | Seconds between polls (default `300`). |
| `STATE_FILE` | Where seen-ids are stored (default `state.json`). |

> Tip: Start a chat with your bot (send it any message) once, or it won't be
> able to message you.

## Usage

```bash
# Verify Telegram credentials
python main.py --test-telegram

# Run a single poll cycle (good for cron or a quick check)
python main.py --once

# Run continuously
python main.py
```

### Running with Docker (recommended)

The listener is a long-lived process, which makes it a good fit for Docker.

```bash
cp .env.example .env      # fill in your credentials + search URL first
docker compose up -d      # build and run in the background
docker compose logs -f    # watch it work
docker compose down       # stop it
```

`docker compose` reads your `.env` for configuration. The seen-ids state is
kept in a named volume (`yad2-state`) mounted at `/data`, so it survives
restarts, rebuilds, and `docker compose down` — you won't get re-alerted about
listings you've already seen. `restart: unless-stopped` brings it back up after
a crash or host reboot.

To run a one-off cycle or test Telegram without the compose service:

```bash
docker build -t yad2-listener .
docker run --rm --env-file .env yad2-listener --test-telegram
docker run --rm --env-file .env -v yad2-state:/data yad2-listener --once
```

The image's `ENTRYPOINT` is `python main.py`, so any flags you pass to
`docker run`/`docker compose run` go straight to the CLI.

### Running under cron

If you'd rather not keep a long-lived process, run `--once` on a schedule.
The `state.json` file carries the "already seen" set between runs:

```cron
*/5 * * * * cd /path/to/yad2-listener && /usr/bin/python main.py --once >> yad2.log 2>&1
```

## Notes on the Yad2 API

Yad2 has no public API; this reads the same private gateway the website uses,
and that gateway's response shape changes from time to time and between
categories. The parser in `yad2_listener/yad2_client.py` is deliberately
lenient — it walks the JSON looking for listing-shaped objects rather than
hard-coding one path — so it tolerates most shape changes. If Yad2 changes
things dramatically and you stop getting results, that parser is the place to
look. Requests use browser-like headers because the gateway sits behind
Cloudflare; if you ever hit blocks, increase `POLL_INTERVAL` to be gentle.

## Development

```bash
pip install pytest
python -m pytest
```

Tests cover the URL translation, the response parser, and the seen-store state
persistence — the pure logic, with no network calls.

## Project layout

```
main.py                          # CLI entry point
yad2_listener/
  config.py                      # env/.env configuration
  yad2_client.py                 # fetch + parse Yad2 feed → Listing objects
  telegram_notifier.py           # Telegram Bot API sender
  state.py                       # persistent set of seen listing ids
  listener.py                    # the poll → dedup → notify loop
tests/                           # unit tests for the pure logic
```
