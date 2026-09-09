"""Locale propagation test for GraphBuilderService.add_text_batches.

`add_text_batches` runs each chunk's storage.add_text() call (which reaches
NERExtractor.extract()) in a `ThreadPoolExecutor` worker. `ContextVar`-based
locale state does NOT propagate into pool workers, so the worker must
capture the active locale on the parent thread and re-apply it (mirrors
PR #194's fix for `report_agent` and the same fix in `graph_tools`,
`simulation_config_generator`, `wonderwall_profile_generator`). This test
guards that NERExtractor sees the caller's locale instead of silently
falling back to English.
"""
import threading

from app.services.graph_builder import GraphBuilderService
from app.utils import i18n


class _RecordingStorage:
    """Fake storage that records the active locale seen inside each worker."""

    def __init__(self):
        self.seen_locales: list[str] = []
        self._lock = threading.Lock()

    def add_text(self, graph_id, text):
        with self._lock:
            self.seen_locales.append(i18n.get_active_locale())
        return f"episode-{text[:4]}"


def test_add_text_batches_threads_locale_into_pool_worker():
    """Without the capture+use_locale fix, get_active_locale() inside the
    pool worker returns the default ("en") regardless of the caller's
    locale. This asserts the caller's zh-CN locale reaches every worker.
    """
    storage = _RecordingStorage()
    service = GraphBuilderService(storage)

    with i18n.use_locale("zh-CN"):
        service.add_text_batches(
            "graph-1", ["chunk one", "chunk two", "chunk three"], max_workers=3
        )

    assert storage.seen_locales, "no worker call recorded"
    assert all(loc == "zh-CN" for loc in storage.seen_locales), (
        f"worker thread(s) did not see caller locale zh-CN, saw {storage.seen_locales} "
        "(locale dropped across ThreadPoolExecutor)"
    )


def test_add_text_batches_defaults_to_en_outside_use_locale():
    """Control: with no active locale set, workers correctly see the default."""
    storage = _RecordingStorage()
    service = GraphBuilderService(storage)

    service.add_text_batches("graph-1", ["chunk one"], max_workers=1)

    assert storage.seen_locales == ["en"]
