# Podcast FR→EN Voxtral

One-shot workflow `podcast-fr-en-voxtral` (served by the `hn-tech-digest` deployment, hardened / on-behalf-of).

Given an Ausha episode page URL (default: the *In Security We Trust* episode with Thomas Baignères, Olvid), it:

1. Resolves the episode MP3 URL from the page HTML / the Ausha RSS feed (`podcast-resolve-episode-audio`).
2. Downloads the MP3 in the worker (the Ausha CDN 403s Mistral's `file_url` fetcher) and transcribes it
   with Voxtral ASR (`voxtral-small-transcribe-3`, `language=fr`, `diarize=true`, segment timestamps,
   context bias for names/terms) via multipart upload (`podcast-transcribe-episode`).
3. Maps diarized `speaker_N` labels to host/guest roles with a chat model (`podcast-assign-speaker-roles`).
4. Translates the transcript French → English in batches, spoken-style for TTS (`podcast-translate-transcript`).
5. Re-voices the interview with `voxtral-mini-tts-3-0`, one preset `voice_id` per speaker
   (default host `voice_1787`, guest `voice_485`), concatenating per-turn MP3s into parts of
   ≤ ~2.7 MB and delivering them (`podcast-synthesize-and-deliver-chunk`,
   `podcast-deliver-transcript`):
   - `delivery="git"` (default): pushes each part as base64 text to
     `<git_output_dir>/.staging/<slug>/<part>.mp3.b64` on `git_branch` via the `github_app`
     connector (the MCP tool channel is text-only, so binary is staged as `.b64`), plus
     `transcript-en.md`, `transcript-fr.md` and a `README.md` under `<git_output_dir>/<slug>/`.
     Decode+concat: `for f in .staging/<slug>/*.b64; do base64 -d "$f"; done > <slug>-en.mp3`
   - `delivery="email"`: emails each MP3 part plus a transcript email (EN/FR) to `recipient`.
   - `delivery="both"`: both.

Run it from Studio or:

```
execute_workflow(workflow_identifier="podcast-fr-en-voxtral", deployment_name="hn-tech-digest", input={
  "episode_page_url": "https://podcast.ausha.co/in-security-we-trust/olvid-thomas-baigneres",
  "delivery": "git",                 # "git" | "email" | "both"
  "git_owner": "elpollodiablo2nd", "git_repo": "test",
  "git_branch": "vibe/podcast-voxtral-75b01f",
  "git_output_dir": "podcast-fr-en-voxtral-output",
  "host_voice_id": "voice_1787",
  "guest_voice_id": "voice_485",
  "max_segments": 0,   # >0 trims to the first N segments (cheap validation run)
  "dry_run": false
})
```

Notes:
- Audio parts never cross the workflow/activity payload boundary (2 MB limit): each chunk activity
  synthesizes and emails its own parts and returns only metadata.
- To rebuild the single file from the emailed parts: `cat <base>-*.mp3 > interview-en.mp3`.
- Preset voices: see the Voxtral 3 voice table in the Mistral docs (`/studio/audio/text-to-speech/voices`).

Tests: `apps/worker/tests/test_podcast_fr_en_voxtral.py` (unit + mocked end-to-end via `create_test_worker`).
