"""Shared time-formatting helpers."""

from datetime import datetime, timezone


def utc_iso8601() -> str:
    """Current UTC time as an ISO-8601 ``YYYY-MM-DDTHH:MM:SSZ`` string.

    The canonical timestamp grammar shared by every export/publish surface
    (repro, archive, notebook, signal, outcome-distribution, signed-result,
    and the dkg / waybackclaw publishers) and the webhook delivery log.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
