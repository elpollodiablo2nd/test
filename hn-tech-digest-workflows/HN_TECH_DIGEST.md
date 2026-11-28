# hn-tech-digest

One-shot, user-triggered workflow (`hn-tech-digest`, on-behalf-of, no schedule) that:

1. Fetches the Hacker News front page through a custom HTTP connector for the
   **Algolia HN API** (`GET /search?tags=front_page`, up to 30 hits in one call). Direct
   worker egress to arbitrary hosts is blocked on Mistral Cloud, so the fetch goes
   through the connectors gateway. The workflow references the connector by **ID**
   (`01a1f923-c102-7478-b0e3-4ee243142e84`, stored name `hacker_news_api_d906`) because
   the plain name `hacker-news-api` does not resolve; if you recreate the connector,
   update `HN_API_CONNECTOR_ID` in `apps/worker/src/worker/workflows/hn_tech_digest.py`.
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

## One-time setup: `hacker-news-api` connector

The workflow declares a second connector slot named **`hacker-news-api`**. Create it once
in Studio (Mistral Cloud blocks direct worker egress to public APIs; connector requests go
through the connectors gateway):

1. Open the [Connectors page](https://console.mistral.ai/connectors/marketplace) in your workspace.
2. **+ Add connector** → **Add a custom connector** → protocol **HTTP**.
3. Server URL: `https://hn.algolia.com/api/v1`. Authentication: **None**.
4. Name it `hacker-news-api` (the API stores it with a suffix, e.g. `hacker_news_api_d906`;
   the workflow resolves the slot by connector **ID**, see above).
5. Import the OpenAPI spec from this repo: `connectors/hacker-news-api.openapi.yaml`
   (upload the file, or paste its contents). It exposes `search_stories` (GET /search)
   and `get_item` (GET /items/{itemId}).
6. If the auth preflight asks for credentials for a no-auth connector, add one default
   credential with empty headers.

## Deploy

Managed, hardened deployment built from this repository:

```text
deployment_name: hn-tech-digest
dockerfile_path: deploy/docker/Dockerfile.worker   (build context: repository root)
hardened: true                                       (required for on_behalf_of)
```
