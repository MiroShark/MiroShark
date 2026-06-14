"""Shared canonical base-URL resolution for public-facing surfaces."""

from flask import request

from ..config import Config


def resolve_public_base_url() -> str:
    """Absolute origin (no trailing slash) for public absolute URLs.

    Prefers the operator-set ``Config.PUBLIC_BASE_URL`` (the single source of
    truth across the feed / sitemap / share-card / oEmbed surfaces) so a
    service reached on ``localhost`` but configured for a public host still
    emits public URLs. Falls back to the request host with
    ``X-Forwarded-Proto`` / ``X-Forwarded-Host`` honoured for reverse-proxy
    deployments. Requires an active Flask request context for the fallback.

    Note: ``watch.py`` and ``webhook_service.py`` deliberately keep their own
    resolvers — the former never prefers ``PUBLIC_BASE_URL``, the latter runs
    without a request context — so they are not consolidated here.
    """
    explicit = (Config.PUBLIC_BASE_URL or "").strip()
    if explicit:
        return explicit.rstrip("/")

    base = (request.host_url or "").rstrip("/")
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    forwarded_host = request.headers.get("X-Forwarded-Host")
    if forwarded_host:
        proto = forwarded_proto or ("https" if request.is_secure else "http")
        base = f"{proto}://{forwarded_host}"
    return base
