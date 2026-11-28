import asyncio
import base64
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import timedelta
from urllib.parse import urlparse

import pydantic

import mistralai.workflows as workflows
from mistralai.workflows import Depends
from mistralai.workflows.plugins.mistralai import (
    ChatCompletionRequest,
    ResponseFormat,
    SystemMessage,
    UserMessage,
    get_mistral_client,
    mistralai_chat_complete,
)
from mistralai.workflows.plugins.mistralai.activities import (
    response_format_from_pydantic_model,
)
from mistralai.workflows.plugins.mistralai.connectors import (
    ToolCallClient,
    connector,
    uses_connectors,
)
from worker.workflows.hn_tech_digest import extract_json_object, extract_text_content

gmail_connector = connector("gmail")

TRANSCRIBE_MODEL = "voxtral-small-transcribe-3"
CHAT_MODEL = "mistral-large-latest"
TTS_MODEL = "voxtral-mini-tts-3-0"
DEFAULT_EPISODE_PAGE_URL = (
    "https://podcast.ausha.co/in-security-we-trust/olvid-thomas-baigneres"
)
DEFAULT_RECIPIENT = "fhaidt@gmail.com"
DEFAULT_HOST_VOICE_ID = "voice_1787"
DEFAULT_GUEST_VOICE_ID = "voice_485"
MAX_PART_MP3_BYTES = 2_700_000
MAX_TTS_INPUT_CHARS = 3_000
CHUNK_CHAR_BUDGET = 7_000
TRANSLATE_BATCH_CHARS = 9_000
ROLE_SAMPLE_SEGMENTS = 24
CONTEXT_BIAS = [
    "Olvid",
    "Thomas Baignères",
    "Léna Jakubowicz",
    "EPFL",
    "AES",
    "CryptoExperts",
    "WhatsApp",
    "Signal",
    "Telegram",
    "Matignon",
    "Clever Cloud",
    "AWS",
    "Élysée",
    "RSSI",
    "DSI",
    "directive Borne",
    "NIS2",
    "DORA",
    "Mistral AI",
]


class PodcastVoxtralInput(pydantic.BaseModel):
    episode_page_url: str = DEFAULT_EPISODE_PAGE_URL
    recipient: str = DEFAULT_RECIPIENT
    host_voice_id: str = DEFAULT_HOST_VOICE_ID
    guest_voice_id: str = DEFAULT_GUEST_VOICE_ID
    max_segments: int = 0
    dry_run: bool = False


class PodcastEpisode(pydantic.BaseModel):
    page_url: str
    show_slug: str
    episode_slug: str
    title: str
    audio_url: str
    duration_seconds: int | None = None


class Segment(pydantic.BaseModel):
    index: int
    start: float
    end: float
    speaker: str
    text: str


class RoleAssignment(pydantic.BaseModel):
    mapping: dict[str, str]
    host_name: str
    guest_name: str


class Turn(pydantic.BaseModel):
    idx: int
    speaker: str
    role: str
    start: float
    end: float
    text_fr: str
    text_en: str = ""


class Transcript(pydantic.BaseModel):
    turns: list[Turn]
    markdown_en: str
    markdown_fr: str


class TranslationItem(pydantic.BaseModel):
    i: int
    en: str


class TranslationBatch(pydantic.BaseModel):
    items: list[TranslationItem]


class FeedItem(pydantic.BaseModel):
    title: str
    link: str
    enclosure_url: str
    duration_seconds: int | None = None


class PartInfo(pydantic.BaseModel):
    filename: str
    bytes: int
    message_id: str | None = None


class ChunkResult(pydantic.BaseModel):
    chunk_index: int
    turns_synthesized: int
    parts: list[PartInfo]


class PodcastVoxtralResult(pydantic.BaseModel):
    episode_title: str
    episode_page_url: str
    audio_url: str
    segment_count: int
    turn_count: int
    host_name: str
    guest_name: str
    speaker_mapping: dict[str, str]
    part_count: int
    parts: list[PartInfo]
    transcript_en: str
    transcript_fr: str
    transcript_message_id: str | None = None
    dry_run: bool = False


def path_slugs(url: str) -> tuple[str, str]:
    parts = [p for p in urlparse(url).path.split("/") if p]
    show = parts[0] if parts else ""
    episode = parts[1] if len(parts) > 1 else ""
    return show, episode


def extract_audio_candidates(html: str) -> list[str]:
    normalized = html.replace("\\/", "/").replace("&amp;", "&")
    patterns = [
        r"https://audio\.ausha\.co/[^\"'\s<>\\]+?\.mp3[^\"'\s<>\\]*",
        r"https://[a-z0-9.-]*ausha[a-z0-9.-]*/[^\"'\s<>\\]+?\.mp3[^\"'\s<>\\]*",
        r"https://[^\"'\s<>\\]+\.mp3[^\"'\s<>\\]*",
    ]
    seen: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, normalized):
            if match not in seen:
                seen.append(match)
        if seen:
            break
    return seen


def extract_feed_ids(html: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"feed\.ausha\.co/([A-Za-z0-9_-]+)", html)))


def page_title(html: str) -> str:
    match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
    if not match:
        match = re.search(r"<title>([^<]+)</title>", html)
    title = match.group(1).strip() if match else "Podcast episode"
    title = re.split(r"\s*\|", title)[0]
    title = re.sub(r"\s+-\s+Ausha$", "", title)
    return title.strip() or "Podcast episode"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, name: str) -> str:
    for child in element:
        if _local(child.tag) == name:
            return (child.text or "").strip()
    return ""


def _child_attr(element: ET.Element, name: str, attr: str) -> str:
    for child in element:
        if _local(child.tag) == name:
            return child.attrib.get(attr, "")
    return ""


def parse_feed_items(xml_text: str) -> list[FeedItem]:
    root = ET.fromstring(xml_text)
    items: list[FeedItem] = []
    for element in root.iter():
        if _local(element.tag) != "item":
            continue
        enclosure = _child_attr(element, "enclosure", "url")
        if not enclosure:
            continue
        duration_text = _child_text(element, "duration")
        duration: int | None = None
        if duration_text:
            parts = duration_text.split(":")
            try:
                if len(parts) == 3:
                    duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                elif len(parts) == 2:
                    duration = int(parts[0]) * 60 + int(parts[1])
                else:
                    duration = int(parts[0])
            except ValueError:
                duration = None
        items.append(
            FeedItem(
                title=_child_text(element, "title"),
                link=_child_text(element, "link"),
                enclosure_url=enclosure,
                duration_seconds=duration,
            )
        )
    return items


def find_episode_in_feed(items: list[FeedItem], episode_slug: str) -> FeedItem | None:
    if not episode_slug:
        return items[0] if items else None
    for item in items:
        if episode_slug in item.link.lower() or episode_slug in item.title.lower().replace(" ", "-"):
            return item
    return None


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:48] or "interview"


def fmt_ts(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def split_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        window = remaining[:max_chars]
        cut = max(
            window.rfind(". "),
            window.rfind("! "),
            window.rfind("? "),
            window.rfind("… "),
            window.rfind(", "),
            window.rfind(" "),
        )
        if cut < max_chars // 2:
            cut = max_chars
        pieces.append(remaining[:cut].strip())
        remaining = remaining[cut:].lstrip()
    if remaining.strip():
        pieces.append(remaining.strip())
    return [p for p in pieces if p]


def merge_turns(segments: list[Segment], roles: RoleAssignment) -> list[Turn]:
    turns: list[Turn] = []
    for segment in segments:
        role = roles.mapping.get(segment.speaker)
        if role not in ("host", "guest"):
            role = "guest"
        if turns and turns[-1].speaker == segment.speaker:
            turns[-1].text_fr = (turns[-1].text_fr + " " + segment.text).strip()
            turns[-1].end = segment.end
        else:
            turns.append(
                Turn(
                    idx=len(turns),
                    speaker=segment.speaker,
                    role=role,
                    start=segment.start,
                    end=segment.end,
                    text_fr=segment.text,
                )
            )
    return turns


def plan_chunks(turns: list[Turn]) -> list[list[Turn]]:
    chunks: list[list[Turn]] = []
    current: list[Turn] = []
    current_chars = 0
    for turn in turns:
        cost = len(turn.text_en) + 1
        if current and current_chars + cost > CHUNK_CHAR_BUDGET:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(turn)
        current_chars += cost
    if current:
        chunks.append(current)
    return chunks


def plan_translation_batches(turns: list[Turn]) -> list[list[Turn]]:
    batches: list[list[Turn]] = []
    current: list[Turn] = []
    current_chars = 0
    for turn in turns:
        cost = len(turn.text_fr) + 24
        if current and current_chars + cost > TRANSLATE_BATCH_CHARS:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(turn)
        current_chars += cost
    if current:
        batches.append(current)
    return batches


def build_markdown(turns: list[Turn], roles: RoleAssignment, episode_title: str, lang: str) -> str:
    host = roles.host_name or "Host"
    guest = roles.guest_name or "Guest"
    lines = [
        f"# {episode_title}",
        "",
        f"- Host: {host}",
        f"- Guest: {guest}",
        "",
    ]
    for turn in turns:
        name = host if turn.role == "host" else guest
        text = turn.text_en if lang == "en" else turn.text_fr
        lines.append(f"**{name}** [{fmt_ts(turn.start)}]: {text}")
        lines.append("")
    return "\n".join(lines)


ROLE_SYSTEM_PROMPT = """You are labeling speakers in a diarized podcast transcript.

The episode is an interview: one host (the interviewer) and one guest (the person being interviewed).
Given the episode title and the first transcript segments with their speaker labels, decide which
speaker label is the host and which is the guest. The host usually introduces the show and the guest
and asks the questions.

Return the RoleAssignment JSON exactly as structured:
- mapping: every speaker label you saw, mapped to "host" or "guest"
- host_name: the host's real name if you can infer it, otherwise "Host"
- guest_name: the guest's real name if you can infer it from the episode title, otherwise "Guest"
Do not wrap the JSON in prose."""

TRANSLATE_SYSTEM_PROMPT = """You translate a French podcast interview transcript into English for text-to-speech narration.

Rules:
- Translate each item faithfully into natural, fluent spoken English. Keep the full meaning, all facts,
  numbers, names and technical terms. Do not summarize, skip, reorder or add anything.
- Write for the ear: remove filler disfluencies (euh, bah, enfin, tu vois, quoi...) and obvious
  self-corrections, keep the flow conversational.
- Keep proper nouns exactly (Olvid, EPFL, AES, WhatsApp, Signal, Telegram, AWS, Clever Cloud,
  Matignon, Élysée, Mistral...). Spell acronyms so they are pronounced sensibly (A.I., E.P.F.L.).
- Keep non-speech tags such as [laughter] as-is. Render numbers in a speakable way.
- Return the TranslationBatch JSON exactly as structured: one item per input index i, with the
  English text in en. Do not wrap the JSON in prose."""


@workflows.activity(
    name="podcast-resolve-episode-audio",
    start_to_close_timeout=timedelta(seconds=120),
    retry_policy_max_attempts=3,
)
async def resolve_episode_audio(episode_page_url: str) -> PodcastEpisode:
    import httpx

    show_slug, episode_slug = path_slugs(episode_page_url)
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=30, headers=headers
    ) as client:
        page = await client.get(episode_page_url)
        page.raise_for_status()
        html = page.text
        candidates = extract_audio_candidates(html)
        feed_ids = extract_feed_ids(html)
        title = page_title(html)
        duration: int | None = None
        audio_url: str | None = None
        for feed_id in feed_ids:
            try:
                feed = await client.get(f"https://feed.ausha.co/{feed_id}")
                feed.raise_for_status()
            except httpx.HTTPError:
                continue
            items = parse_feed_items(feed.text)
            match = find_episode_in_feed(items, episode_slug)
            if match is not None:
                audio_url = match.enclosure_url
                duration = match.duration_seconds
                if match.title:
                    title = match.title
                break
    if audio_url is None:
        if not candidates:
            raise workflows.WorkflowError(
                "podcast_audio_url_not_found", non_retryable=True
            )
        audio_url = candidates[0]
    if len(audio_url) > 2083:
        raise workflows.WorkflowError(
            "podcast_audio_url_too_long", non_retryable=True
        )
    return PodcastEpisode(
        page_url=episode_page_url,
        show_slug=show_slug,
        episode_slug=episode_slug,
        title=title,
        audio_url=audio_url,
        duration_seconds=duration,
    )


async def download_episode_audio(audio_url: str) -> bytes:
    import httpx

    header_variants = [
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://podcast.ausha.co/",
            "Accept": "audio/mpeg,audio/*;q=0.9,*/*;q=0.8",
        },
        {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "*/*",
        },
        {"User-Agent": "curl/8.5.0", "Accept": "*/*"},
    ]
    last_error = ""
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=httpx.Timeout(60.0, read=900.0)
    ) as http:
        for headers in header_variants:
            try:
                response = await http.get(audio_url, headers=headers)
            except httpx.RequestError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                continue
            if response.status_code == 200 and len(response.content) > 100_000:
                return response.content
            last_error = f"HTTP {response.status_code} ({len(response.content)} bytes)"
    raise workflows.WorkflowError(
        f"podcast_audio_download_failed: {last_error}", non_retryable=True
    )


@workflows.activity(
    name="podcast-transcribe-episode",
    start_to_close_timeout=timedelta(seconds=1800),
    retry_policy_max_attempts=2,
)
async def transcribe_episode(episode: PodcastEpisode) -> list[Segment]:
    client = get_mistral_client()
    audio_bytes = await download_episode_audio(episode.audio_url)
    file_name = f"{slugify(episode.title)[:48] or 'episode'}.mp3"
    response = await asyncio.to_thread(
        client.audio.transcriptions.complete,
        model=TRANSCRIBE_MODEL,
        file={"file_name": file_name, "content": audio_bytes},
        language="fr",
        diarize=True,
        timestamp_granularities=["segment"],
        context_bias=CONTEXT_BIAS,
    )
    segments: list[Segment] = []
    for raw in response.segments or []:
        text = (getattr(raw, "text", "") or "").strip()
        if not text:
            continue
        speaker = getattr(raw, "speaker_id", None) or "speaker_1"
        segments.append(
            Segment(
                index=len(segments),
                start=float(getattr(raw, "start", 0.0) or 0.0),
                end=float(getattr(raw, "end", 0.0) or 0.0),
                speaker=str(speaker),
                text=text,
            )
        )
    segments.sort(key=lambda s: (s.start, s.end))
    for index, segment in enumerate(segments):
        segment.index = index
    if not segments:
        raise workflows.WorkflowError(
            "podcast_transcription_empty", non_retryable=True
        )
    return segments


@workflows.activity(
    name="podcast-assign-speaker-roles",
    start_to_close_timeout=timedelta(seconds=240),
    retry_policy_max_attempts=3,
)
async def assign_speaker_roles(
    segments: list[Segment], episode_title: str
) -> RoleAssignment:
    sample = segments[:ROLE_SAMPLE_SEGMENTS]
    listing = "\n".join(
        f"{s.speaker} @{s.start:.0f}s: {s.text[:220]}" for s in sample
    )
    speakers = sorted({s.speaker for s in segments})
    request = ChatCompletionRequest(
        model=CHAT_MODEL,
        messages=[
            SystemMessage(content=ROLE_SYSTEM_PROMPT),
            UserMessage(
                content=(
                    f"Episode title: {episode_title}\n\n"
                    f"First segments:\n{listing}\n\n"
                    f"All speaker labels in the full transcript: {', '.join(speakers)}"
                )
            ),
        ],
        temperature=0.0,
        response_format=ResponseFormat.model_validate(
            response_format_from_pydantic_model(RoleAssignment)
        ),
    )
    response = await mistralai_chat_complete(request)
    content = extract_text_content(response.choices[0].message.content)
    roles = RoleAssignment.model_validate_json(extract_json_object(content))
    for speaker in speakers:
        if roles.mapping.get(speaker) not in ("host", "guest"):
            roles.mapping[speaker] = "host" if speaker == speakers[0] else "guest"
    return roles


@workflows.activity(
    name="podcast-translate-transcript",
    start_to_close_timeout=timedelta(seconds=1800),
    retry_policy_max_attempts=2,
)
async def translate_transcript(
    segments: list[Segment], roles: RoleAssignment, episode_title: str
) -> Transcript:
    turns = merge_turns(segments, roles)
    batches = plan_translation_batches(turns)
    for batch in batches:
        listing = "\n".join(f"[{t.idx}] {t.speaker}: {t.text_fr}" for t in batch)
        request = ChatCompletionRequest(
            model=CHAT_MODEL,
            messages=[
                SystemMessage(content=TRANSLATE_SYSTEM_PROMPT),
                UserMessage(
                    content=(
                        f"Episode: {episode_title}\n\n"
                        f"Translate these French segments to English:\n\n{listing}"
                    )
                ),
            ],
            temperature=0.2,
            response_format=ResponseFormat.model_validate(
                response_format_from_pydantic_model(TranslationBatch)
            ),
        )
        response = await mistralai_chat_complete(request)
        content = extract_text_content(response.choices[0].message.content)
        translated = TranslationBatch.model_validate_json(extract_json_object(content))
        by_index = {item.i: item.en for item in translated.items}
        for turn in batch:
            turn.text_en = (by_index.get(turn.idx) or "").strip() or turn.text_fr
    return Transcript(
        turns=turns,
        markdown_en=build_markdown(turns, roles, episode_title, "en"),
        markdown_fr=build_markdown(turns, roles, episode_title, "fr"),
    )


async def _send_gmail(
    gmail: ToolCallClient,
    recipient: str,
    subject: str,
    body: str,
    attachments: list[dict],
) -> dict:
    result = await gmail.call_tool(
        tool_name="send_email",
        arguments={
            "to": [recipient],
            "subject": subject,
            "body": body,
            "attachments": attachments,
        },
    )
    if isinstance(result, dict):
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            return structured
        content = result.get("content")
        if isinstance(content, list):
            import json

            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    try:
                        parsed = json.loads(block.get("text", ""))
                        if isinstance(parsed, dict):
                            return parsed
                    except (ValueError, TypeError):
                        continue
        return result
    return {}


@workflows.activity(
    name="podcast-synthesize-and-email-chunk",
    start_to_close_timeout=timedelta(seconds=3600),
    retry_policy_max_attempts=2,
)
async def synthesize_and_email_chunk(
    turns: list[Turn],
    chunk_index: int,
    total_chunks: int,
    recipient: str,
    subject: str,
    episode_title: str,
    base_filename: str,
    host_voice_id: str,
    guest_voice_id: str,
    dry_run: bool,
    gmail: ToolCallClient = Depends(gmail_connector),
) -> ChunkResult:
    client = get_mistral_client()
    buffer = b""
    parts: list[PartInfo] = []

    async def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        filename = f"{base_filename}-c{chunk_index:02d}p{len(parts) + 1:02d}.mp3"
        message_id: str | None = None
        if not dry_run:
            sent = await _send_gmail(
                gmail,
                recipient,
                f"{subject} — audio part {filename}",
                (
                    f"Audio part {filename} of the English Voxtral narration of: "
                    f"{episode_title}.\n\nConcatenate all parts in filename order to rebuild "
                    f"the full interview MP3, e.g.: cat {base_filename}-*.mp3 > {base_filename}.mp3"
                ),
                [
                    {
                        "filename": filename,
                        "mimeType": "audio/mpeg",
                        "content": base64.b64encode(buffer).decode(),
                    }
                ],
            )
            message_id = sent.get("id")
        parts.append(PartInfo(filename=filename, bytes=len(buffer), message_id=message_id))
        buffer = b""

    for turn in turns:
        voice_id = host_voice_id if turn.role == "host" else guest_voice_id
        for piece in split_text(turn.text_en, MAX_TTS_INPUT_CHARS):
            response = await client.audio.speech.complete_async(
                model=TTS_MODEL,
                input=piece,
                voice_id=voice_id,
                response_format="mp3",
            )
            buffer += base64.b64decode(response.audio_data)
            if len(buffer) >= MAX_PART_MP3_BYTES:
                await flush()
    await flush()
    return ChunkResult(
        chunk_index=chunk_index,
        turns_synthesized=len(turns),
        parts=parts,
    )


@workflows.activity(
    name="podcast-send-transcript-email",
    start_to_close_timeout=timedelta(seconds=120),
    retry_policy_max_attempts=2,
)
async def send_transcript_email(
    recipient: str,
    subject: str,
    episode: PodcastEpisode,
    markdown_en: str,
    markdown_fr: str,
    part_count: int,
    gmail: ToolCallClient = Depends(gmail_connector),
) -> dict:
    body = (
        f"English (and French) transcript of: {episode.title}\n"
        f"Episode page: {episode.page_url}\n"
        f"Original audio: {episode.audio_url}\n\n"
        f"The English audio narration ({part_count} MP3 part(s), two voices: host and guest) "
        f"arrives in separate emails with 'audio part' in the subject. Concatenate the parts "
        f"in filename order to rebuild the full interview MP3.\n\n"
        "Attachments: transcript-en.md (English), transcript-fr.md (original French)."
    )
    return await _send_gmail(
        gmail,
        recipient,
        f"{subject} — transcript (EN/FR)",
        body,
        [
            {
                "filename": "transcript-en.md",
                "mimeType": "text/markdown",
                "content": base64.b64encode(markdown_en.encode()).decode(),
            },
            {
                "filename": "transcript-fr.md",
                "mimeType": "text/markdown",
                "content": base64.b64encode(markdown_fr.encode()).decode(),
            },
        ],
    )


@workflows.workflow.define(
    name="podcast-fr-en-voxtral",
    workflow_display_name="Podcast FR→EN Voxtral",
    workflow_description=(
        "One-shot, user-triggered podcast translation + narration: resolves the episode audio "
        "from an Ausha page URL, transcribes it with Voxtral ASR (French, with speaker "
        "diarization), translates the transcript to English, re-voices the interview with "
        "voxtral-mini-tts-3-0 using a different preset voice per speaker, and emails the "
        "transcript (EN/FR) plus the MP3 audio parts to the recipient's Gmail."
    ),
    on_behalf_of=True,
)
@uses_connectors(gmail_connector)
class PodcastFrEnVoxtralWorkflow:
    @workflows.workflow.entrypoint
    async def run(self, input: PodcastVoxtralInput) -> PodcastVoxtralResult:
        episode = await resolve_episode_audio(input.episode_page_url)
        segments = await transcribe_episode(episode)
        if input.max_segments > 0:
            segments = segments[: input.max_segments]
        roles = await assign_speaker_roles(segments, episode.title)
        transcript = await translate_transcript(segments, roles, episode.title)
        chunks = plan_chunks(transcript.turns)
        subject = f"[Voxtral EN] {episode.title[:80]}"
        base = slugify(episode.title)
        parts: list[PartInfo] = []
        total = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            result = await synthesize_and_email_chunk(
                chunk,
                index,
                total,
                input.recipient,
                subject,
                episode.title,
                base,
                input.host_voice_id,
                input.guest_voice_id,
                input.dry_run,
            )
            parts.extend(result.parts)
        sent: dict = {}
        if not input.dry_run:
            sent = await send_transcript_email(
                input.recipient,
                subject,
                episode,
                transcript.markdown_en,
                transcript.markdown_fr,
                len(parts),
            )
        return PodcastVoxtralResult(
            episode_title=episode.title,
            episode_page_url=episode.page_url,
            audio_url=episode.audio_url,
            segment_count=len(segments),
            turn_count=len(transcript.turns),
            host_name=roles.host_name,
            guest_name=roles.guest_name,
            speaker_mapping=roles.mapping,
            part_count=len(parts),
            parts=parts,
            transcript_en=transcript.markdown_en,
            transcript_fr=transcript.markdown_fr,
            transcript_message_id=sent.get("id"),
            dry_run=input.dry_run,
        )
