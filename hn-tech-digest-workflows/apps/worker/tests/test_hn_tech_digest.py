import asyncio
import base64
from datetime import timedelta

import mistralai.workflows as workflows
from mistralai.workflows.testing import create_test_worker

from worker.workflows.hn_tech_digest import (
    Digest,
    DigestStory,
    HnStory,
    HnTechDigestInput,
    HnTechDigestWorkflow,
    build_story_listing,
    extract_json_object,
    extract_sent_message,
    extract_text_content,
    parse_algolia_hit,
    render_digest_html,
    story_domain,
    unwrap_tool_result,
)

WORKFLOW_EXECUTION_TIMEOUT = timedelta(seconds=30)


def make_story(story_id: int = 1, title: str = "Example raises funding") -> HnStory:
    return HnStory(
        id=story_id,
        title=title,
        url="https://www.example.com/post",
        score=321,
        by="pg",
        descendants=123,
        hn_url=f"https://news.ycombinator.com/item?id={story_id}",
    )


def make_digest() -> Digest:
    return Digest(
        date="2026-11-20",
        stories=[
            DigestStory(
                rank=1,
                title="Example raises $100M Series C",
                url="https://www.example.com/post",
                hn_url="https://news.ycombinator.com/item?id=1",
                score=321,
                comments=123,
                summary="Example Corp raised a $100M Series C led by Example Ventures.",
            )
        ],
        digest_markdown="# HN Tech Digest — 2026-11-20\n\n1. [Example raises $100M Series C](https://www.example.com/post)",
        podcast_script="Here is your Hacker News tech digest for November 20th, 2026. "
        "First up, Example Corp raised a hundred million dollar Series C. That is all for today.",
    )


def test_parse_algolia_hit_accepts_story_hits():
    hit = {
        "objectID": "42",
        "title": "A launch",
        "url": "https://blog.example.org/a",
        "points": 10,
        "author": "dang",
        "num_comments": 5,
    }
    story = parse_algolia_hit(hit)
    assert story is not None
    assert story.id == 42
    assert story.score == 10
    assert story.descendants == 5
    assert story.by == "dang"
    assert story.hn_url == "https://news.ycombinator.com/item?id=42"
    assert story_domain(story.url) == "blog.example.org"


def test_parse_algolia_hit_rejects_bad_hits():
    assert parse_algolia_hit({"objectID": "1"}) is None
    assert parse_algolia_hit({"title": "no id"}) is None
    assert parse_algolia_hit({"objectID": "abc", "title": "bad id"}) is None
    assert parse_algolia_hit("not a dict") is None


def test_story_domain_defaults_to_hn():
    assert story_domain(None) == "news.ycombinator.com"
    assert story_domain("https://www.sub.example.com/a") == "sub.example.com"


def test_build_story_listing_contains_metadata():
    listing = build_story_listing([make_story()])
    assert "id=1" in listing
    assert "score=321" in listing
    assert "Example raises funding" in listing
    assert "example.com" in listing


def test_render_digest_html_escapes_and_links():
    digest = make_digest()
    digest.stories[0].title = 'Evil <script> & "quotes"'
    html = render_digest_html(digest)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert 'href="https://www.example.com/post"' in html
    assert "HN discussion" in html


def test_unwrap_tool_result_handles_plain_mcp_and_structured_shapes():
    assert unwrap_tool_result({"id": "m1"}) == {"id": "m1"}
    mcp_shape = {"content": [{"type": "text", "text": '{"hits": [1, 2]}'}]}
    assert unwrap_tool_result(mcp_shape) == {"hits": [1, 2]}
    assert unwrap_tool_result({"structuredContent": {"hits": []}}) == {"hits": []}
    not_json = {"content": [{"type": "text", "text": "not json"}]}
    assert unwrap_tool_result(not_json) is None
    assert unwrap_tool_result(None) is None


def test_extract_sent_message_handles_plain_and_mcp_shapes():
    assert extract_sent_message({"id": "m1", "threadId": "t1"}) == {
        "id": "m1",
        "threadId": "t1",
    }
    mcp_shape = {
        "content": [{"type": "text", "text": '{"id": "m2", "threadId": "t2"}'}]
    }
    assert extract_sent_message(mcp_shape) == {"id": "m2", "threadId": "t2"}
    assert (
        extract_sent_message({"content": [{"type": "text", "text": "not json"}]}) == {}
    )
    assert extract_sent_message(None) == {}


def test_extract_text_content_handles_str_and_chunks():
    assert extract_text_content("plain") == "plain"
    chunks = [
        {"type": "think", "thinking": "hmm"},
        type("C", (), {"type": "text", "text": '{"a": 1}'})(),
        type("C", (), {"type": "text", "text": " tail"})(),
    ]
    assert extract_text_content(chunks) == '{"a": 1} tail'
    assert extract_text_content(None) == "None"


def test_extract_json_object_finds_object_in_prose_and_fences():
    assert extract_json_object('{"a": 1}') == '{"a": 1}'
    assert extract_json_object('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert extract_json_object('Here you go: {"a": {"b": 2}} thanks') == '{"a": {"b": 2}}'
    try:
        extract_json_object("no json here")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_input_defaults():
    model = HnTechDigestInput()
    assert model.recipient
    assert model.voice_id
    assert model.max_stories >= 1
    assert model.dry_run is False


@workflows.activity(name="fetch-front-page-stories")
async def mock_fetch_front_page_stories(limit: int) -> list[HnStory]:
    return [make_story(1), make_story(2, "Second story")]


@workflows.activity(name="build-tech-digest")
async def mock_build_tech_digest(
    stories: list[HnStory], max_stories: int, today: str
) -> Digest:
    digest = make_digest()
    digest.stories = digest.stories[:max_stories]
    return digest


@workflows.activity(name="generate-podcast-audio")
async def mock_generate_podcast_audio(script: str, voice_id: str) -> str:
    assert script
    assert voice_id
    return base64.b64encode(b"fake-mp3-bytes").decode()


@workflows.activity(name="send-digest-email")
async def mock_send_digest_email(
    recipient: str,
    subject: str,
    body_markdown: str,
    html_body: str,
    audio_b64: str,
    audio_filename: str,
) -> dict:
    assert recipient
    assert subject
    assert audio_b64
    assert audio_filename.endswith(".mp3")
    assert "<ol>" in html_body
    return {"id": "msg-1", "threadId": "thr-1"}


async def test_workflow_end_to_end_with_mocked_activities(temporal_env) -> None:
    async with create_test_worker(
        temporal_env,
        workflows=[HnTechDigestWorkflow],
        activities=[
            mock_fetch_front_page_stories,
            mock_build_tech_digest,
            mock_generate_podcast_audio,
            mock_send_digest_email,
        ],
    ):
        handle = await temporal_env.client.start_workflow(
            "hn-tech-digest",
            {"recipient": "me@example.com", "dry_run": False},
            id="test-hn-tech-digest",
            task_queue="test-task-queue",
            execution_timeout=WORKFLOW_EXECUTION_TIMEOUT,
        )
        result = await asyncio.wait_for(handle.result(), timeout=45)
        assert result["recipient"] == "me@example.com"
        assert result["story_count"] == 1
        assert result["email_message_id"] == "msg-1"
        assert result["email_thread_id"] == "thr-1"
        assert result["audio_filename"].endswith(".mp3")
        assert result["audio_bytes"] > 0
        assert result["dry_run"] is False


async def test_workflow_dry_run_skips_email(temporal_env) -> None:
    async with create_test_worker(
        temporal_env,
        workflows=[HnTechDigestWorkflow],
        activities=[
            mock_fetch_front_page_stories,
            mock_build_tech_digest,
            mock_generate_podcast_audio,
        ],
    ):
        handle = await temporal_env.client.start_workflow(
            "hn-tech-digest",
            {"dry_run": True},
            id="test-hn-tech-digest-dry",
            task_queue="test-task-queue",
            execution_timeout=WORKFLOW_EXECUTION_TIMEOUT,
        )
        result = await asyncio.wait_for(handle.result(), timeout=45)
        assert result["dry_run"] is True
        assert result["email_message_id"] is None
        assert result["audio_filename"] is None
        assert result["story_count"] == 1
