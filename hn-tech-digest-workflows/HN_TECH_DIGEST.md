# hn-tech-digest

One-shot, user-triggered workflow (`hn-tech-digest`, on-behalf-of, no schedule) that:

1. Fetches the Hacker News front page via the official Firebase API
   (`/v0/frontpage.json` + `/v0/item/{id}.json`, first 30 items by default).
2. Asks `mistral-large-latest` to select the top **tech-industry** stories (excludes personal
   blogs, essays, and non-tech news) and returns a structured `Digest`: per-story summaries, a
   Markdown digest, and a 180-260 word podcast script (~1-2 minutes spoken).
3. Renders the script to MP3 with Voxtral TTS (`voxtral-mini-tts-3-0`, voice `gb_jane_neutral`
   by default).
4. Sends the digest to your own Gmail inbox through the `gmail` connector `send_email` tool,
   with the MP3 attached (`audio/mpeg`).

Because the workflow is `on_behalf_of=True`, each run uses the **triggering user's** Gmail
credential; it therefore requires a **hardened** managed deployment.

## Trigger (one-shot, no schedule)

- In Mistral Studio: Workflows → `hn-tech-digest` → **Start workflow**.
- Or via API/MCP: `execute_workflow(workflow_identifier="hn-tech-digest", input={})`.

## Input (`HnTechDigestInput`)

| Field | Default | Description |
| --- | --- | --- |
| `recipient` | `fhaidt@gmail.com` | Where the digest email is sent. |
| `voice_id` | `gb_jane_neutral` | Voxtral TTS voice slug for the MP3. |
| `max_stories` | `8` | Max stories in the digest. |
| `front_page_limit` | `30` | How many front-page items to fetch. |
| `dry_run` | `false` | If `true`, everything runs except the email send (used for testing). |

## Deploy

Managed, hardened deployment built from this repository:

```text
deployment_name: hn-tech-digest
dockerfile_path: deploy/docker/Dockerfile.worker   (build context: repository root)
hardened: true                                       (required for on_behalf_of)
```
