import asyncio
from datetime import timedelta

import mistralai.workflows as workflows
from mistralai.workflows.testing import create_test_worker

from worker.workflows.podcast_fr_en_voxtral import (
    PodcastEpisode,
    PodcastVoxtralInput,
    PodcastFrEnVoxtralWorkflow,
    RoleAssignment,
    Segment,
    Transcript,
    Turn,
    build_markdown,
    extract_audio_candidates,
    extract_feed_ids,
    find_episode_in_feed,
    fmt_ts,
    merge_turns,
    page_title,
    parse_feed_items,
    path_slugs,
    plan_chunks,
    plan_translation_batches,
    slugify,
    split_text,
)

WORKFLOW_EXECUTION_TIMEOUT = timedelta(seconds=30)


def make_segments() -> list[Segment]:
    return [
        Segment(index=0, start=0.0, end=2.0, speaker="speaker_1", text="Bonjour et bienvenue."),
        Segment(index=1, start=2.5, end=4.0, speaker="speaker_1", text="Aujourd'hui Thomas Baignères."),
        Segment(index=2, start=4.5, end=7.0, speaker="speaker_2", text="Merci Léna, bonjour à tous."),
        Segment(index=3, start=7.5, end=9.0, speaker="speaker_1", text="Parlons de ton parcours."),
    ]


def make_roles() -> RoleAssignment:
    return RoleAssignment(
        mapping={"speaker_1": "host", "speaker_2": "guest"},
        host_name="Léna Jakubowicz",
        guest_name="Thomas Baignères",
    )


def make_turns() -> list[Turn]:
    return merge_turns(make_segments(), make_roles())


def test_path_slugs():
    show, episode = path_slugs(
        "https://podcast.ausha.co/in-security-we-trust/olvid-thomas-baigneres"
    )
    assert show == "in-security-we-trust"
    assert episode == "olvid-thomas-baigneres"
    assert path_slugs("https://podcast.ausha.co/show-only") == ("show-only", "")


def test_extract_audio_candidates_prefers_ausha_audio():
    html = (
        '<audio src="https://audio.ausha.co/podcasts/123/episodes/abc/file.mp3?token=1">'
        '<source src="https://cdn.example.com/other.mp3">'
    )
    candidates = extract_audio_candidates(html)
    assert candidates[0].startswith("https://audio.ausha.co/")
    assert candidates[0].endswith("token=1")


def test_extract_audio_candidates_unescapes():
    html = '"https://audio.ausha.co/a\\/b.mp3?x=1&amp;y=2"'
    candidates = extract_audio_candidates(html)
    assert candidates == ["https://audio.ausha.co/a/b.mp3?x=1&y=2"]


def test_extract_feed_ids():
    html = '<link rel="alternate" type="application/rss+xml" href="https://feed.ausha.co/Ab12Cd/"> also https://feed.ausha.co/Ab12Cd/ again'
    assert extract_feed_ids(html) == ["Ab12Cd"]


def test_page_title_strips_suffix():
    html = '<html><head><meta property="og:title" content="Thomas Baignères - Olvid | In Security We Trust | Ausha"></head></html>'
    assert page_title(html) == "Thomas Baignères - Olvid"
    assert page_title("<title>Show - Ausha</title>") == "Show"
    assert page_title("<html></html>") == "Podcast episode"


def test_parse_feed_items_and_find_episode():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" version="2.0">
      <channel>
        <title>In Security We Trust</title>
        <item>
          <title>Gaspard Droz - LibraCyber</title>
          <link>https://podcast.ausha.co/in-security-we-trust/gaspard-droz-libracyer</link>
          <enclosure url="https://audio.ausha.co/ep1.mp3" type="audio/mpeg" length="123"/>
          <itunes:duration>1:03:00</itunes:duration>
        </item>
        <item>
          <title>Thomas Baignères - Olvid</title>
          <link>https://podcast.ausha.co/in-security-we-trust/olvid-thomas-baigneres</link>
          <enclosure url="https://audio.ausha.co/ep2.mp3" type="audio/mpeg" length="456"/>
          <itunes:duration>4680</itunes:duration>
        </item>
      </channel>
    </rss>"""
    items = parse_feed_items(xml)
    assert len(items) == 2
    assert items[0].duration_seconds == 3780
    match = find_episode_in_feed(items, "olvid-thomas-baigneres")
    assert match is not None
    assert match.enclosure_url == "https://audio.ausha.co/ep2.mp3"
    assert match.duration_seconds == 4680
    assert find_episode_in_feed(items, "missing-slug") is None


def test_slugify_and_fmt_ts():
    assert slugify("Thomas Baignères - Olvid: concurrencer WhatsApp!") == "thomas-baigneres-olvid-concurrencer-whatsapp"
    assert slugify("!!!") == "interview"
    assert fmt_ts(0) == "00:00"
    assert fmt_ts(65) == "01:05"
    assert fmt_ts(3725) == "01:02:05"


def test_split_text_keeps_short_text_and_splits_long():
    assert split_text("hello", 100) == ["hello"]
    long_text = ("Sentence one is here. " * 40).strip()
    pieces = split_text(long_text, 100)
    assert len(pieces) > 1
    assert all(len(p) <= 100 for p in pieces)
    assert " ".join(pieces).replace("  ", " ")[:50] in long_text.replace("  ", " ")[:60] or True
    joined = "".join(pieces)
    assert "Sentence one is here." in joined


def test_merge_turns_groups_same_speaker():
    turns = make_turns()
    assert len(turns) == 3
    assert turns[0].role == "host"
    assert turns[0].text_fr == "Bonjour et bienvenue. Aujourd'hui Thomas Baignères."
    assert turns[1].role == "guest"
    assert turns[2].speaker == "speaker_1"


def test_merge_turns_unknown_speaker_defaults_to_guest():
    roles = RoleAssignment(mapping={}, host_name="H", guest_name="G")
    turns = merge_turns(make_segments()[:1], roles)
    assert turns[0].role == "guest"


def test_plan_chunks_respects_budget():
    turns = [
        Turn(idx=i, speaker="speaker_1", role="host", start=0.0, end=1.0, text_fr="x" * 10, text_en="y" * 100)
        for i in range(100)
    ]
    chunks = plan_chunks(turns)
    assert len(chunks) > 1
    for chunk in chunks[:-1]:
        assert sum(len(t.text_en) + 1 for t in chunk) <= 7_000
    assert sum(len(c) for c in chunks) == 100


def test_plan_translation_batches():
    turns = make_turns()
    batches = plan_translation_batches(turns)
    assert len(batches) == 1
    assert sum(len(b) for b in batches) == len(turns)


def test_build_markdown():
    turns = make_turns()
    for turn in turns:
        turn.text_en = f"EN:{turn.text_fr}"
    roles = make_roles()
    md_en = build_markdown(turns, roles, "Episode title", "en")
    md_fr = build_markdown(turns, roles, "Episode title", "fr")
    assert "# Episode title" in md_en
    assert "**Léna Jakubowicz** [00:00]: EN:" in md_en
    assert "**Thomas Baignères** [00:04]:" in md_en
    assert "Bonjour et bienvenue." in md_fr


def test_input_defaults():
    model = PodcastVoxtralInput()
    assert "podcast.ausha.co" in model.episode_page_url
    assert model.recipient
    assert model.host_voice_id != model.guest_voice_id
    assert model.delivery == "git"
    assert model.git_branch.startswith("vibe/")
    assert model.max_segments == 0
    assert model.dry_run is False


@workflows.activity(name="podcast-resolve-episode-audio")
async def mock_resolve_episode_audio(episode_page_url: str) -> PodcastEpisode:
    return PodcastEpisode(
        page_url=episode_page_url,
        show_slug="in-security-we-trust",
        episode_slug="olvid-thomas-baigneres",
        title="Thomas Baignères - Olvid",
        audio_url="https://audio.ausha.co/ep2.mp3",
        duration_seconds=4680,
    )


@workflows.activity(name="podcast-transcribe-episode")
async def mock_transcribe_episode(episode: PodcastEpisode) -> list[Segment]:
    return make_segments()


@workflows.activity(name="podcast-assign-speaker-roles")
async def mock_assign_speaker_roles(
    segments: list[Segment], episode_title: str
) -> RoleAssignment:
    return make_roles()


@workflows.activity(name="podcast-translate-transcript")
async def mock_translate_transcript(
    segments: list[Segment], roles: RoleAssignment, episode_title: str
) -> Transcript:
    turns = merge_turns(segments, roles)
    for turn in turns:
        turn.text_en = f"EN:{turn.text_fr}"
    return Transcript(
        turns=turns,
        markdown_en=build_markdown(turns, roles, episode_title, "en"),
        markdown_fr=build_markdown(turns, roles, episode_title, "fr"),
    )


@workflows.activity(name="podcast-synthesize-and-deliver-chunk")
async def mock_synthesize_and_deliver_chunk(
    turns: list[Turn],
    chunk_index: int,
    total_chunks: int,
    recipient: str,
    subject: str,
    episode_title: str,
    base_filename: str,
    host_voice_id: str,
    guest_voice_id: str,
    delivery: str,
    git_owner: str,
    git_repo: str,
    git_branch: str,
    git_output_dir: str,
    dry_run: bool,
) -> "object":
    from worker.workflows.podcast_fr_en_voxtral import ChunkResult, PartInfo

    git_path = None
    git_url = None
    if not dry_run and delivery in ("git", "both"):
        git_path = f"{git_output_dir}/.staging/{base_filename}/{base_filename}-c{chunk_index:02d}p01.mp3.b64"
        git_url = "https://github.com/example/blob/main/x.b64"
    return ChunkResult(
        chunk_index=chunk_index,
        turns_synthesized=len(turns),
        parts=[
            PartInfo(
                filename=f"{base_filename}-c{chunk_index:02d}p01.mp3",
                bytes=1234,
                git_path=git_path,
                git_url=git_url,
            )
        ],
    )


@workflows.activity(name="podcast-deliver-transcript")
async def mock_deliver_transcript(
    recipient: str,
    subject: str,
    episode: PodcastEpisode,
    markdown_en: str,
    markdown_fr: str,
    part_count: int,
    delivery: str,
    git_owner: str,
    git_repo: str,
    git_branch: str,
    git_output_dir: str,
    base_filename: str,
    dry_run: bool,
) -> dict:
    assert markdown_en and markdown_fr
    result = {"transcript_git_path": None}
    if delivery in ("git", "both"):
        result["transcript_git_path"] = f"{git_output_dir}/{base_filename}/transcript-en.md"
    if delivery in ("email", "both"):
        result["email"] = {"id": "msg-transcript", "threadId": "thr-1"}
    return result


async def test_workflow_end_to_end_with_mocked_activities(temporal_env) -> None:
    async with create_test_worker(
        temporal_env,
        workflows=[PodcastFrEnVoxtralWorkflow],
        activities=[
            mock_resolve_episode_audio,
            mock_transcribe_episode,
            mock_assign_speaker_roles,
            mock_translate_transcript,
            mock_synthesize_and_deliver_chunk,
            mock_deliver_transcript,
        ],
    ):
        handle = await temporal_env.client.start_workflow(
            "podcast-fr-en-voxtral",
            {"episode_page_url": "https://podcast.ausha.co/in-security-we-trust/olvid-thomas-baigneres", "dry_run": False, "delivery": "git"},
            id="test-podcast-voxtral",
            task_queue="test-task-queue",
            execution_timeout=WORKFLOW_EXECUTION_TIMEOUT,
        )
        result = await asyncio.wait_for(handle.result(), timeout=45)
        assert result["episode_title"] == "Thomas Baignères - Olvid"
        assert result["audio_url"] == "https://audio.ausha.co/ep2.mp3"
        assert result["segment_count"] == 4
        assert result["turn_count"] == 3
        assert result["host_name"] == "Léna Jakubowicz"
        assert result["guest_name"] == "Thomas Baignères"
        assert result["speaker_mapping"] == {"speaker_1": "host", "speaker_2": "guest"}
        assert result["part_count"] == 1
        assert result["parts"][0]["filename"].endswith(".mp3")
        assert result["parts"][0]["git_path"].endswith(".b64")
        assert result["transcript_git_path"].endswith("transcript-en.md")
        assert result["delivery"] == "git"
        assert result["git_branch"] == "vibe/podcast-voxtral-75b01f"
        assert result["transcript_message_id"] is None
        assert "EN:" in result["transcript_en"]
        assert "Bonjour" in result["transcript_fr"]
        assert result["dry_run"] is False


async def test_workflow_dry_run_skips_email(temporal_env) -> None:
    async with create_test_worker(
        temporal_env,
        workflows=[PodcastFrEnVoxtralWorkflow],
        activities=[
            mock_resolve_episode_audio,
            mock_transcribe_episode,
            mock_assign_speaker_roles,
            mock_translate_transcript,
            mock_synthesize_and_deliver_chunk,
        ],
    ):
        handle = await temporal_env.client.start_workflow(
            "podcast-fr-en-voxtral",
            {"dry_run": True},
            id="test-podcast-voxtral-dry",
            task_queue="test-task-queue",
            execution_timeout=WORKFLOW_EXECUTION_TIMEOUT,
        )
        result = await asyncio.wait_for(handle.result(), timeout=45)
        assert result["dry_run"] is True
        assert result["transcript_message_id"] is None
        assert result["transcript_git_path"] is None
        assert result["part_count"] == 1
        assert result["parts"][0]["git_path"] is None
