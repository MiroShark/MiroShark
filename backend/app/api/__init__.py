"""
API Routes Module
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)
templates_bp = Blueprint('templates', __name__)
settings_bp = Blueprint('settings', __name__)
observability_bp = Blueprint('observability', __name__)
mcp_bp = Blueprint('mcp', __name__)
docs_bp = Blueprint('docs', __name__)
feed_bp = Blueprint('feed', __name__)
countries_bp = Blueprint('countries', __name__)

from . import graph  # noqa: E402, F401
from . import simulation  # noqa: E402, F401
from . import report  # noqa: E402, F401
from . import templates  # noqa: E402, F401
from . import settings  # noqa: E402, F401
from . import observability  # noqa: E402, F401
from . import mcp  # noqa: E402, F401
from . import docs  # noqa: E402, F401
from . import feed  # noqa: E402, F401
from . import countries  # noqa: E402, F401

# share_bp is mounted at the root (no /api prefix) so the public landing
# URL stays clean — see api/share.py.
from .share import share_bp  # noqa: E402, F401

# watch_bp is mounted at the root (no /api prefix) so /watch/<sim_id>
# stays a clean shareable URL — see api/watch.py.
from .watch import watch_bp  # noqa: E402, F401

# sitemap_bp is mounted at the root (no /api prefix) so /sitemap.xml
# and /robots.txt land where crawlers expect them — see api/sitemap.py.
from .sitemap import sitemap_bp  # noqa: E402, F401

# notifications_bp serves /api/config/notifications — a public config
# probe that tells the SPA which channels (webhook / Discord / Slack)
# are wired up on this deployment without leaking the URLs themselves.
from .notifications import notifications_bp  # noqa: E402, F401

# stats_bp serves /api/stats + /api/stats/badge.svg — the first
# endpoints that describe the platform itself rather than one
# simulation. See app/api/stats.py.
from .stats import stats_bp  # noqa: E402, F401

# project_stats_bp serves /api/project/<project_id>/stats — the
# per-project sibling of /api/stats. Mounted at /api/project so the
# URL stays a clean operator-facing surface. See app/api/stats.py.
from .stats import project_stats_bp  # noqa: E402, F401

# surfaces_bp serves /api/surfaces.json — the machine-readable
# catalog of every share / platform surface this deployment
# exposes. Platform-level sibling of stats_bp. See app/api/surfaces.py.
from .surfaces import surfaces_bp  # noqa: E402, F401

# status_bp serves /api/status.json — the platform health probe.
# Sibling of stats_bp + surfaces_bp; answers "is the platform up and
# completing sims?" for external status monitors (Upptime,
# BetterUptime, Statuspage.io) without leaking the analytics envelope
# /api/stats returns. See app/api/status.py.
from .status import status_bp  # noqa: E402, F401

# activity_bp serves /api/activity.json — the lightweight
# "what just completed?" polling primitive. Sibling of stats_bp /
# status_bp / surfaces_bp; sits between the full filterable gallery
# (/api/simulation/public) and the subscription-style feed surfaces
# (/api/feed.rss + /api/feed.atom). Built for keyless integrator
# polling — Aeon push-recap, status dashboards, social bots. See
# app/api/activity.py.
from .activity import activity_bp  # noqa: E402, F401

