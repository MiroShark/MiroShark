"""
Demographic sampler — pulls grounded persona seeds from NVIDIA Nemotron parquet
datasets so the LLM persona generator can anchor each agent in a real census-like
row (age, sex, geography, occupation, education, industry) instead of inventing
demographics from thin air.

Ported from MiroWorld's persona_sampler.py and trimmed:
  * single sample() entry point
  * DuckDB columnar filter over a parquet glob
  * lazy huggingface_hub download on first use
  * graceful no-op when duckdb / huggingface_hub aren't installed, so the
    feature stays fully optional and the rest of the backend boots without
    the extra deps

Wiring: WonderwallProfileGenerator calls sample_seeds() once per simulation
when a country config is selected; the returned rows are paired with entities
and injected into the persona-generation prompt as an additional grounding
block. Graph-context and web-enrichment layers run on top unchanged.
"""

from __future__ import annotations

import glob
import os
import random
import re
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from . import country_registry

logger = get_logger('miroshark.demographic_sampler')


_CACHE_DIR_DEFAULT = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'nemotron')


def _try_import_duckdb():
    try:
        import duckdb  # type: ignore
        return duckdb
    except Exception:  # noqa: BLE001
        return None


def _try_import_hf():
    try:
        from huggingface_hub import snapshot_download  # type: ignore
        return snapshot_download
    except Exception:  # noqa: BLE001
        return None


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_ident(name: str) -> str:
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name or ''):
        raise ValueError(f"Invalid column name: {name!r}")
    return f'"{name}"'


def _resolve_parquet_glob(country_cfg: Dict[str, Any]) -> Optional[str]:
    """Return a usable parquet glob for the country, downloading from HF on first
    use if no local snapshot exists. Returns None if neither path is available."""
    ds = country_cfg.get('dataset') or {}
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    repo_root = os.path.abspath(os.path.join(backend_dir, '..'))

    # 1. local paths
    for raw in ds.get('local_paths') or []:
        for base in (repo_root, backend_dir):
            candidate = raw if os.path.isabs(raw) else os.path.join(base, raw)
            if glob.glob(candidate):
                return candidate

    # 2. HF download
    repo_id = ds.get('repo_id')
    if not repo_id:
        return None
    snapshot_download = _try_import_hf()
    if snapshot_download is None:
        logger.warning(
            "huggingface_hub not installed; cannot download Nemotron dataset for "
            f"{country_cfg.get('code')}. `pip install huggingface_hub` to enable."
        )
        return None

    download_dir = ds.get('download_dir') or os.path.join(
        _CACHE_DIR_DEFAULT, country_cfg.get('code', 'default')
    )
    download_dir = download_dir if os.path.isabs(download_dir) else os.path.join(repo_root, download_dir)
    os.makedirs(download_dir, exist_ok=True)
    try:
        snapshot_download(
            repo_id=repo_id,
            repo_type='dataset',
            allow_patterns=ds.get('allow_patterns') or ['data/train-*', 'README.md'],
            local_dir=download_dir,
            max_workers=4,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Nemotron snapshot_download failed for {repo_id}: {e}")
        return None

    glob_pat = os.path.join(download_dir, 'data', 'train-*')
    if glob.glob(glob_pat):
        return glob_pat
    return None


def sample_seeds(
    country_code: str,
    *,
    limit: int,
    seed: int = 42,
    geography_values: Optional[List[str]] = None,
    min_age: Optional[int] = None,
    max_age: Optional[int] = None,
    sexes: Optional[List[str]] = None,
    occupations: Optional[List[str]] = None,
    education_levels: Optional[List[str]] = None,
    industries: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Sample up to `limit` demographic rows for the given country.

    Returns an empty list (with a warning) when duckdb/hf deps are missing,
    when the country code is unknown, or when no parquet is reachable —
    callers should treat the feature as additive, not required.
    """
    if limit <= 0:
        return []

    cfg = country_registry.get(country_code)
    if cfg is None:
        logger.info(f"Unknown country '{country_code}'; skipping demographic seed.")
        return []

    duckdb = _try_import_duckdb()
    if duckdb is None:
        logger.warning(
            "duckdb not installed; demographic sampling disabled. "
            "`pip install duckdb` to enable."
        )
        return []

    parquet_glob = _resolve_parquet_glob(cfg)
    if not parquet_glob:
        logger.warning(f"No parquet snapshot resolvable for country '{country_code}'.")
        return []

    geo_field = (cfg.get('geography') or {}).get('field')
    conn = duckdb.connect()
    try:
        cols = {row[0] for row in conn.execute(
            f"DESCRIBE SELECT * FROM read_parquet({_sql_quote(parquet_glob)})"
        ).fetchall()}

        where: List[str] = []
        if min_age is not None and 'age' in cols:
            where.append(f"age >= {int(min_age)}")
        if max_age is not None and 'age' in cols:
            where.append(f"age <= {int(max_age)}")
        if geography_values and geo_field in cols:
            where.append(_in_clause(geo_field, geography_values))
        if sexes and 'sex' in cols:
            where.append(_in_clause('sex', sexes))
        if occupations and 'occupation' in cols:
            where.append(_in_clause('occupation', occupations))
        if education_levels and 'education_level' in cols:
            where.append(_in_clause('education_level', education_levels))
        if industries and 'industry' in cols:
            where.append(_in_clause('industry', industries))

        where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''
        # Deterministic shuffle keyed on seed + a stable column so reproducibility
        # holds across re-runs of the same scenario.
        order_col = next((c for c in ('uuid', 'persona', 'occupation', 'age') if c in cols), None)
        if order_col:
            order_expr = (
                f"hash(coalesce(CAST({_sql_ident(order_col)} AS VARCHAR), '') || '{int(seed)}')"
            )
        else:
            order_expr = f"hash('{int(seed)}')"

        query = f"""
            SELECT *
            FROM read_parquet({_sql_quote(parquet_glob)})
            {where_sql}
            ORDER BY {order_expr}
            LIMIT {int(limit)}
        """
        rows = conn.execute(query).fetch_df().to_dict(orient='records')
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Demographic sample query failed for {country_code}: {e}")
        return []
    finally:
        conn.close()

    # Tag rows with the geography field so prompt builders can show it generically.
    for row in rows:
        if geo_field and row.get(geo_field) is not None:
            row['_geography_field'] = geo_field
            row['_geography_value'] = str(row.get(geo_field))
    return rows


def _in_clause(column: str, values: List[Any]) -> str:
    ident = _sql_ident(column)
    norm = [str(v).strip().lower() for v in values if str(v).strip()]
    if not norm:
        return '1=1'
    rendered = ', '.join(_sql_quote(v) for v in norm)
    return f"lower(CAST({ident} AS VARCHAR)) IN ({rendered})"


def infer_filter_schema(
    country_code: str,
    *,
    max_distinct: int = 250,
) -> List[Dict[str, Any]]:
    """Introspect the country's parquet schema and return cohort-selector hints.

    For each `filter_fields` entry declared in the country pack:
      - type "range": resolve min/max from the parquet column
      - other types: return up to `max_distinct` distinct values, ordered

    Used by the SPA's cohort selector to populate dropdowns/chips without
    hardcoding the option lists per country. Returns [] when duckdb isn't
    installed, when no parquet is reachable, or when the country code is
    unknown — UI should treat the response as additive guidance.
    """
    cfg = country_registry.get(country_code)
    if cfg is None:
        return []
    declared = cfg.get('filter_fields') or []
    if not declared:
        return []

    duckdb = _try_import_duckdb()
    if duckdb is None:
        logger.warning(
            "duckdb not installed; filter-schema inference disabled. "
            "`pip install duckdb` to enable."
        )
        return []

    parquet_glob = _resolve_parquet_glob(cfg)
    if not parquet_glob:
        return []

    conn = duckdb.connect()
    try:
        cols = {row[0] for row in conn.execute(
            f"DESCRIBE SELECT * FROM read_parquet({_sql_quote(parquet_glob)})"
        ).fetchall()}

        out: List[Dict[str, Any]] = []
        for entry in declared:
            field = str(entry.get('field') or '').strip()
            ftype = str(entry.get('type') or '').strip()
            label = str(entry.get('label') or field).strip() or field
            if not field or not ftype:
                continue
            # Schema uses 'sex' on disk; the UI may declare 'gender' for friendlier copy.
            column = 'sex' if field.lower() == 'gender' else field
            if column not in cols:
                continue

            payload: Dict[str, Any] = {
                "field": field,
                "type": ftype,
                "label": label,
            }
            ident = _sql_ident(column)

            if ftype == 'range':
                row = conn.execute(
                    f"SELECT MIN({ident}), MAX({ident}) "
                    f"FROM read_parquet({_sql_quote(parquet_glob)}) "
                    f"WHERE {ident} IS NOT NULL"
                ).fetchone()
                if row:
                    payload['min'] = row[0]
                    payload['max'] = row[1]
                if 'default_min' in entry:
                    payload['default_min'] = entry['default_min']
                if 'default_max' in entry:
                    payload['default_max'] = entry['default_max']
            else:
                rows = conn.execute(
                    f"SELECT DISTINCT CAST({ident} AS VARCHAR) AS v "
                    f"FROM read_parquet({_sql_quote(parquet_glob)}) "
                    f"WHERE {ident} IS NOT NULL "
                    f"  AND TRIM(CAST({ident} AS VARCHAR)) <> '' "
                    f"ORDER BY v "
                    f"LIMIT {int(max_distinct)}"
                ).fetchall()
                payload['options'] = [str(r[0]) for r in rows if r and str(r[0]).strip()]
            out.append(payload)
        return out
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Filter-schema inference failed for {country_code}: {e}")
        return []
    finally:
        conn.close()


def format_seed_for_prompt(seed: Dict[str, Any]) -> str:
    """Render a Nemotron row as a short, prompt-friendly anchor block.

    Strips internal `_*` keys and any null/empty values; keeps the fields the
    persona generator can actually use to tilt the persona toward a realistic
    demographic.
    """
    if not seed:
        return ''
    interesting = (
        'age', 'sex', 'marital_status', 'education_level', 'occupation',
        'industry', 'cultural_background', 'income_bracket', 'household_income',
        'planning_area', 'state', 'province', 'region', 'district', 'city',
        'country', 'hobby', 'skill', 'persona',
    )
    parts: List[str] = []
    for key in interesting:
        val = seed.get(key)
        if val is None:
            continue
        text = str(val).strip()
        if not text or text.lower() == 'nan':
            continue
        parts.append(f"- {key}: {text}")
    geo_field = seed.get('_geography_field')
    geo_value = seed.get('_geography_value')
    if geo_field and geo_value and geo_field not in interesting:
        parts.append(f"- {geo_field}: {geo_value}")
    return '\n'.join(parts)


def pair_entities_with_seeds(
    n_entities: int,
    seeds: List[Dict[str, Any]],
    *,
    rng: Optional[random.Random] = None,
) -> List[Optional[Dict[str, Any]]]:
    """Return a list of length n_entities, each slot a seed dict or None.

    When seeds are fewer than entities, the remaining slots are None and those
    entities fall back to the graph-only persona pipeline.
    """
    if not seeds:
        return [None] * n_entities
    rng = rng or random.Random(42)
    pool = list(seeds)
    rng.shuffle(pool)
    out: List[Optional[Dict[str, Any]]] = []
    for i in range(n_entities):
        out.append(pool[i] if i < len(pool) else None)
    return out
