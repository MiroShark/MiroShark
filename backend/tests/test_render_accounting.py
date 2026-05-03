import pytest

from app.services.render_accounting import (
    assert_render_allowed,
    current_day,
    provider_count_today,
    record_render_event,
    accounting_summary,
)


def test_record_render_event_counts_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_IMAGE_DAILY_LIMIT", "5")
    session = {}
    record_render_event(session, provider="openai", model="gpt-image-2", slide_index=0, bytes=123, size="1024x1536")

    assert provider_count_today(session, "openai") == 1
    summary = accounting_summary(session)
    assert summary["openai_used_today"] == 1
    assert summary["openai_remaining_today"] == 4
    assert summary["total"]["openai"] == 1


def test_openai_summary_counts_openai_provider_variants(monkeypatch):
    monkeypatch.setenv("OPENAI_IMAGE_DAILY_LIMIT", "3")
    session = {}
    record_render_event(session, provider="openai-strict-reference-edit", model="gpt-image-2", slide_index=0, bytes=123)
    record_render_event(session, provider="openai", model="gpt-image-2", slide_index=1, bytes=456)

    assert provider_count_today(session, "openai") == 2
    summary = accounting_summary(session)
    assert summary["openai_used_today"] == 2
    assert summary["openai_remaining_today"] == 1


def test_assert_render_allowed_blocks_over_limit(monkeypatch):
    monkeypatch.setenv("OPENAI_IMAGE_DAILY_LIMIT", "1")
    session = {}
    record_render_event(session, provider="openai", model="gpt-image-2", slide_index=0, bytes=123)

    with pytest.raises(RuntimeError, match="daily limit exceeded"):
        assert_render_allowed(session, "openai", requested=1)


def test_assert_render_allowed_ignores_non_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_IMAGE_DAILY_LIMIT", "0")
    assert_render_allowed({}, "nano_banana", requested=100)
