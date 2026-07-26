# Auto-deploy with Komodo

Goal: every push to `main` makes Komodo **pull the repo and redeploy** the
compose stack (rebuilding the image), with no manual `git pull` / `docker
compose up`.

There are two pieces: a **Komodo Stack** (what to deploy) and a **GitHub
webhook** (what triggers a deploy on push).

## 0. Stop the manual deployment first

If you've been running `docker compose up` by hand in a checked-out copy, stop
it before handing the stack to Komodo — the fixed `container_name: yad2-listener`
means only one can run at a time:

```bash
cd ~/projects/yad2-listener
docker compose down
```

Komodo manages its own clone of the repo, so you don't deploy from
`~/projects/...` anymore once this is set up.

## 1. Create the Stack

**Option A — as code (recommended):** add a Komodo *Resource Sync* pointing at
this repo, file path `deploy/komodo-stack.toml`. Komodo creates/updates the
`yad2-listener` stack from that file. Edit `server`, `git_account`, and the
`environment` values in the TOML to match your setup.

**Option B — in the UI:** Stacks → New Stack, then set:

| Field | Value |
| --- | --- |
| Server | your server (e.g. `srv1515969`) |
| Git repo | `andreyshindler/yad2-listener`, branch `main` |
| Run directory | `.` |
| Compose file | `docker-compose.yml` |
| Extra args | `--build`  *(so the image rebuilds on every deploy)* |
| Environment | your `TELEGRAM_*`, `YAD2_SEARCH_URL`, `POLL_INTERVAL` (Komodo writes these to `.env`, which the compose reads) |

Deploy once manually to confirm it comes up (`docker compose logs` should show
`Captured N gateway payload(s)`).

## 2. Turn on the webhook

1. On the Stack page in Komodo, enable **Webhooks** and open the webhook
   section — Komodo shows the exact **Deploy** webhook URL to copy. It looks
   like:

   ```
   https://<your-komodo-domain>/listener/github/stack/yad2-listener/deploy
   ```

2. Note your Komodo **webhook secret** — either the global
   `KOMODO_WEBHOOK_SECRET` from your Komodo Core config, or a per-stack secret
   you set on the Stack.

3. In GitHub: repo → **Settings → Webhooks → Add webhook**:
   - **Payload URL:** the Deploy URL from step 1
   - **Content type:** `application/json`
   - **Secret:** the webhook secret from step 2
   - **Events:** *Just the push event*
   - **Active:** yes

That's it. Komodo only acts on pushes to the stack's configured branch
(`main`), so pushes to other branches are ignored.

## 3. Verify

Push any commit to `main` (or click **Redeliver** on the GitHub webhook's
"Recent Deliveries"). You should see:

- GitHub webhook delivery → **200** response
- A new deployment in the Stack's **Updates/Deployments** history in Komodo
- `docker compose logs -f` on the server showing the container restart

## Notes

- **State is preserved:** the `yad2-state` named volume (holding `state.json`)
  persists across redeploys because the compose project name is stable, so you
  won't get re-alerted about old listings after a deploy.
- **Rebuilds:** the `--build` extra arg is what makes code changes take effect;
  without it `docker compose up` would reuse the cached `yad2-listener` image.
- **Secrets:** prefer entering the Telegram/token values in Komodo's Stack
  environment (or Komodo secrets) rather than committing them — `.env` is
  git-ignored and Komodo generates it at deploy time.
- Field names and the exact webhook path can differ slightly between Komodo
  versions; the Stack page in the UI is authoritative — copy the webhook URL
  from there if it differs from the example above.
