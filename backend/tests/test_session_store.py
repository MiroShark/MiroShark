"""Tests for SessionStore — JSON file-backed session persistence."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def store(tmp_path):
    from app.storage.session_store import SessionStore
    return SessionStore(base_dir=tmp_path)


def test_create_returns_session_with_new_id_and_timestamps(store):
    s = store.create()
    assert "id" in s and len(s["id"]) > 0
    assert "created_at" in s
    assert "updated_at" in s
    assert s["messages"] == []
    assert s["seed_state"] == {}


def test_create_writes_file(store, tmp_path):
    s = store.create()
    expected = tmp_path / f"{s['id']}.json"
    assert expected.exists()
    saved = json.loads(expected.read_text())
    assert saved["id"] == s["id"]


def test_save_persists_session(store, tmp_path):
    s = store.create()
    s["messages"] = [{"role": "user", "content": "hi"}]
    s["title"] = "Test session"
    store.save(s)

    saved = json.loads((tmp_path / f"{s['id']}.json").read_text())
    assert saved["messages"] == [{"role": "user", "content": "hi"}]
    assert saved["title"] == "Test session"


def test_save_updates_updated_at(store):
    s = store.create()
    original_updated = s["updated_at"]
    s["messages"].append({"role": "user", "content": "hi"})
    store.save(s)

    loaded = store.load(s["id"])
    assert loaded["updated_at"] >= original_updated


def test_load_returns_saved_data(store):
    s = store.create()
    s["title"] = "Loaded"
    store.save(s)

    loaded = store.load(s["id"])
    assert loaded["id"] == s["id"]
    assert loaded["title"] == "Loaded"


def test_load_missing_returns_none(store):
    assert store.load("nonexistent-id") is None


def test_list_returns_summaries_sorted_by_updated_desc(store):
    import time
    a = store.create()
    a["title"] = "First"
    store.save(a)
    time.sleep(0.01)
    b = store.create()
    b["title"] = "Second"
    store.save(b)
    time.sleep(0.01)
    a["title"] = "First (touched)"
    store.save(a)

    summaries = store.list()
    assert len(summaries) == 2
    assert summaries[0]["id"] == a["id"]
    assert summaries[1]["id"] == b["id"]
    assert "title" in summaries[0]
    assert "updated_at" in summaries[0]
    assert "messages" not in summaries[0]


def test_list_empty_returns_empty_list(store):
    assert store.list() == []


def test_delete_removes_file(store, tmp_path):
    s = store.create()
    path = tmp_path / f"{s['id']}.json"
    assert path.exists()

    store.delete(s["id"])
    assert not path.exists()
    assert store.load(s["id"]) is None


def test_base_dir_created_if_missing(tmp_path):
    from app.storage.session_store import SessionStore
    new_dir = tmp_path / "doesnotexist"
    assert not new_dir.exists()
    SessionStore(base_dir=new_dir)
    assert new_dir.exists()
