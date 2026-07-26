# yad2-listener

Monitor a [Yad2](https://www.yad2.co.il) search and get a **Telegram** message
whenever a new listing shows up — for apartments, cars, second-hand items, or
anything else Yad2 lists.

It polls your search on an interval, remembers which listings it has already
seen (in a small JSON file), and only alerts you about genuinely new ones.

## How it works

1. You give it a normal Yad2 search-page URL (the one in your browser bar).
2. It loads that page in a **real Chromium** browser (via Playwright). Yad2 is
   protected by Radware Bot Manager — a JavaScript bot challenge that plain HTTP
   clients can't pass — so a real browser is used to get through it. In Docker
   the browser runs **headful under Xvfb** (a virtual display), which is much
   harder for the bot manager to fingerprint than headless mode.
3. It captures the JSON the page itself fetches from Yad2's `gw.yad2.co.il`
   gateway (already past the bot challenge), falling back to the page's
   server-rendered `__NEXT_DATA__` blob if needed.
4. New listing ids (ones not in `state.json`) are sent to your Telegram chat.
5. It sleeps for `POLL_INTERVAL` seconds and repeats.

The first cycle just records a baseline of the currently-live listings so you
don't get flooded with alerts for everything that already exists.

> Because it drives a real browser, **Docker is the recommended way to run it** —
> the image ships Chromium and everything it needs. See below.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium   # one-time: download the headless browser
cp .env.example .env
```

> On Docker you can skip the `playwright install` step — the image already
> includes Chromium.

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

There's a `Makefile` wrapping the common commands, so you can also just run:

```bash
make up      # build and start in the background
make logs    # follow the logs
make down    # stop
make once    # run a single poll cycle
make help    # list all targets
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

### CI (GitHub Actions)

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the test suite on
every push and pull request, then **sends the result to your Telegram bot**
(✅/❌ with the branch, commit, and a link to the run).

For the Telegram notification, add two repo secrets under **Settings → Secrets
and variables → Actions**:

| Secret | Value |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | your bot token |
| `TELEGRAM_CHAT_ID` | your chat id |

If those secrets aren't set, CI still runs the tests and just skips the
notification.

### Continuous deployment with Komodo

To auto-pull and redeploy on every push to `main`, see
[`deploy/KOMODO.md`](deploy/KOMODO.md). It sets up a Komodo Stack (defined as
code in [`deploy/komodo-stack.toml`](deploy/komodo-stack.toml)) plus a GitHub
webhook, so a `git push` triggers Komodo to pull the repo and rebuild/redeploy
the compose automatically. The `yad2-state` volume persists across deploys, so
you won't get re-alerted about old listings.

### Running under cron

If you'd rather not keep a long-lived process, run `--once` on a schedule.
The `state.json` file carries the "already seen" set between runs:

```cron
*/5 * * * * cd /path/to/yad2-listener && /usr/bin/python main.py --once >> yad2.log 2>&1
```

## Notes on the Yad2 API

Yad2 has no public API and sits behind **Radware Bot Manager**, a JavaScript
bot challenge. A plain HTTP request just gets the challenge page back, which is
why this project drives a headless browser instead: the browser solves the
challenge, and we capture the JSON the page fetches from `gw.yad2.co.il`.

The parser in `yad2_listener/yad2_client.py` is deliberately lenient — it walks
the captured JSON looking for listing-shaped objects rather than hard-coding one
path — so it tolerates Yad2's frequent shape changes. If Yad2 changes things
dramatically and you stop getting results, that parser (and the browser fetch
around it) is the place to look. Keep `POLL_INTERVAL` reasonable (the default
5 minutes is fine) so you're gentle on their servers.

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
