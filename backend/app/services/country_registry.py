"""
Country config registry — loads pluggable country packs from app/countries/*.json.

Each pack declares a Nemotron-style demographic dataset (HuggingFace repo id +
optional local parquet paths), a geography field with its valid values, and the
filter UI hints the frontend uses to build a cohort selector. Ported from
MiroWorld's YAML country configs and trimmed to the columns MiroShark actually
consumes.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger('miroshark.country_registry')

_COUNTRIES_DIR = os.path.join(os.path.dirname(__file__), '..', 'countries')


def _load_all() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if not os.path.isdir(_COUNTRIES_DIR):
        return out
    for fname in sorted(os.listdir(_COUNTRIES_DIR)):
        if not fname.endswith('.json'):
            continue
        path = os.path.join(_COUNTRIES_DIR, fname)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Skipping country pack {fname}: {e}")
            continue
        code = str(data.get('code', '') or '').strip().lower()
        if not code:
            logger.warning(f"Skipping country pack {fname}: missing 'code'")
            continue
        out[code] = data
    return out


_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def all_countries(refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    global _CACHE
    if _CACHE is None or refresh:
        _CACHE = _load_all()
    return _CACHE


def get(code: str) -> Optional[Dict[str, Any]]:
    if not code:
        return None
    return all_countries().get(code.strip().lower())


def list_summaries() -> List[Dict[str, Any]]:
    """Public-safe summary list — strips dataset paths/repo ids."""
    items: List[Dict[str, Any]] = []
    for code, cfg in all_countries().items():
        geo = cfg.get('geography') or {}
        items.append({
            "code": code,
            "name": cfg.get('name', code.upper()),
            "flag_emoji": cfg.get('flag_emoji', ''),
            "available": bool(cfg.get('available', True)),
            "geography_field": geo.get('field'),
            "geography_label": geo.get('label'),
            "geography_count": len(geo.get('values') or []),
            "max_agents": cfg.get('max_agents'),
            "default_agents": cfg.get('default_agents'),
        })
    return items
