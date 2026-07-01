"""
Configuration management
Loads configuration uniformly from the .env file in the project root directory
"""

import os
from dotenv import load_dotenv

# Load the .env file from the project root directory
# Path: MiroShark/.env (relative to backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # If no .env in root directory, try loading environment variables (for production)
    load_dotenv(override=True)


class Config:
    """Flask configuration class"""

    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'miroshark-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON configuration - disable ASCII escaping, display non-ASCII characters directly (instead of \uXXXX format)
    JSON_AS_ASCII = False
    
    # LLM configuration (unified OpenAI format)
    # LLM_PROVIDER: "openai" (default, any OpenAI-compatible API) or "claude-code" (local CLI)
    # Default model is used for profile generation, sim config, memory compaction.
    # Cloud preset: inception/mercury-2:nitro (diffusion LLM — picked for speed;
    # off the report's quality path. Fallback for any unset tier.)
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'openai')
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME') or 'inception/mercury-2:nitro'  # `or` so a blank LLM_MODEL_NAME= falls back instead of sending an empty model

    # Smart model — stronger model for intelligence-sensitive workflows
    # (report generation, ontology extraction, graph reasoning).
    # Defaults to google/gemini-3-flash-preview (stable JSON, fast reports);
    # set SMART_MODEL_NAME= (empty) to inherit the default LLM config above.
    SMART_PROVIDER = os.environ.get('SMART_PROVIDER', '')   # "openai", "claude-code", or empty (inherit)
    SMART_API_KEY = os.environ.get('SMART_API_KEY', '')
    SMART_BASE_URL = os.environ.get('SMART_BASE_URL', '')
    SMART_MODEL_NAME = os.environ.get('SMART_MODEL_NAME', 'google/gemini-3-flash-preview')
    
    # Neo4j configuration
    NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', 'miroshark')

    # Embedding configuration
    # EMBEDDING_PROVIDER: "ollama" (default) uses /api/embed, "openai" uses /v1/embeddings
    EMBEDDING_PROVIDER = os.environ.get('EMBEDDING_PROVIDER', 'ollama')
    EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'nomic-embed-text')
    EMBEDDING_BASE_URL = os.environ.get('EMBEDDING_BASE_URL', 'http://localhost:11434')
    EMBEDDING_API_KEY = os.environ.get('EMBEDDING_API_KEY', '')
    EMBEDDING_DIMENSIONS = int(os.environ.get('EMBEDDING_DIMENSIONS', '768'))
    # How many texts to send per embedding HTTP request. OpenAI/OpenRouter
    # text-embedding-3-* accepts 2048; Ollama nomic-embed-text happily chews
    # through 128+. Lower if your provider 413s you.
    EMBEDDING_BATCH_SIZE = int(os.environ.get('EMBEDDING_BATCH_SIZE', '128'))

    # Reranker configuration — cross-encoder reranking over hybrid search results.
    # Default: BAAI/bge-reranker-v2-m3 (multilingual, ~568M params). Downloaded on first
    # use via sentence-transformers. Disable by setting RERANKER_ENABLED=false.
    RERANKER_ENABLED = os.environ.get('RERANKER_ENABLED', 'true').lower() == 'true'
    RERANKER_MODEL = os.environ.get('RERANKER_MODEL', 'BAAI/bge-reranker-v2-m3')
    # Number of candidates to pull from hybrid fusion before reranking.
    # Must be >= final limit. Larger = better recall before rerank, slower inference.
    RERANKER_CANDIDATES = int(os.environ.get('RERANKER_CANDIDATES', '30'))
    # Torch device for the reranker. Blank = auto (CUDA if available, else CPU).
    # MPS (Apple-Silicon GPU) is intentionally avoided in auto mode — torch can
    # hang compiling Metal shader pipelines for this cross-encoder. Set to
    # 'cpu', 'cuda', or 'mps' to override.
    RERANKER_DEVICE = os.environ.get('RERANKER_DEVICE', '').strip()

    # Graph-traversal retrieval (Zep/Graphiti-style BFS from seed entities).
    # A third retrieval strategy alongside vector + BM25 — catches multi-hop
    # connections where the relevant fact isn't semantically close to the query
    # but is graph-adjacent to a matched entity.
    GRAPH_SEARCH_ENABLED = os.environ.get('GRAPH_SEARCH_ENABLED', 'true').lower() == 'true'
    GRAPH_SEARCH_HOPS = int(os.environ.get('GRAPH_SEARCH_HOPS', '1'))  # 1 or 2
    GRAPH_SEARCH_SEEDS = int(os.environ.get('GRAPH_SEARCH_SEEDS', '5'))  # seed entities per query

    # Entity resolution — Graphiti-style dedup at ingestion time.
    # Fuzzy name + vector similarity find candidates; LLM adjudicates ambiguous
    # ones. Prevents duplicate nodes like "NeuralCoin" / "Neural Coin" / "NC".
    ENTITY_RESOLUTION_ENABLED = os.environ.get('ENTITY_RESOLUTION_ENABLED', 'true').lower() == 'true'
    # Whether to invoke the LLM for ambiguous matches (cheap: one batched call
    # per chunk). Set false to skip LLM and rely on auto-merge threshold alone.
    ENTITY_RESOLUTION_USE_LLM = os.environ.get('ENTITY_RESOLUTION_USE_LLM', 'true').lower() == 'true'

    # Automatic contradiction detection — when a new relation is ingested
    # between the same endpoint pair as an existing one, an LLM judges whether
    # the new fact supersedes the old. Contradicted edges are invalidated
    # (not deleted) so the historical record is preserved.
    CONTRADICTION_DETECTION_ENABLED = os.environ.get(
        'CONTRADICTION_DETECTION_ENABLED', 'true'
    ).lower() == 'true'

    # Community / cluster subgraph (Graphiti tier 3). "Zoom out" layer for the
    # report agent — Leiden clusters entities, LLM writes a title + summary
    # per cluster, stored as :Community nodes with MEMBER_OF edges.
    COMMUNITY_MIN_SIZE = int(os.environ.get('COMMUNITY_MIN_SIZE', '3'))    # drop tiny clusters
    COMMUNITY_MAX_COUNT = int(os.environ.get('COMMUNITY_MAX_COUNT', '30')) # cap per rebuild

    # Reasoning-trace persistence — store the report agent's ReACT loop as
    # a traversable subgraph (:Report → :ReportSection → :ReasoningStep) so
    # reports become re-queryable and reasoning patterns are mineable.
    REASONING_TRACE_ENABLED = os.environ.get(
        'REASONING_TRACE_ENABLED', 'true'
    ).lower() == 'true'

    # File upload configuration
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # Text processing configuration
    DEFAULT_CHUNK_SIZE = 1500  # Larger chunks = fewer NER calls + better entity context
    DEFAULT_CHUNK_OVERLAP = 100  # More overlap prevents splitting entities at boundaries
    
    # Wonderwall simulation configuration
    WONDERWALL_DEFAULT_MAX_ROUNDS = int(os.environ.get('WONDERWALL_DEFAULT_MAX_ROUNDS', '10'))
    WONDERWALL_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')

    # Wonderwall platform available actions configuration
    WONDERWALL_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    WONDERWALL_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    WONDERWALL_POLYMARKET_ACTIONS = [
        'browse_markets', 'buy_shares', 'sell_shares',
        'view_portfolio', 'create_market', 'comment_on_market', 'do_nothing'
    ]
    
    # Web Enrichment — LLM-powered research for persona generation
    # Triggers for notable figures (politicians, CEOs, etc.) or when graph context is thin
    WEB_ENRICHMENT_ENABLED = os.environ.get('WEB_ENRICHMENT_ENABLED', 'true').lower() == 'true'
    # Dedicated model for web research (web_research + deep_research + url_fetch).
    # Defaults to deepseek/deepseek-v4-flash:online (bake-off value winner). Any
    # ":online" OpenRouter variant works; set WEB_SEARCH_MODEL= (empty) to inherit
    # the default LLM (only viable if the default model can browse).
    WEB_SEARCH_MODEL = os.environ.get('WEB_SEARCH_MODEL', 'deepseek/deepseek-v4-flash:online')

    # SearXNG metasearch — when set, web enrichment does real search-then-
    # synthesize with the DEFAULT LLM instead of requiring a websearch-enabled
    # model (:online). Falls back to WEB_SEARCH_MODEL when unset or on failure.
    SEARXNG_BASE_URL = (os.environ.get('MIROSHARK_SEARXNG_BASE_URL', '') or '').strip().rstrip('/')
    SEARXNG_TIMEOUT = int(os.environ.get('MIROSHARK_SEARXNG_TIMEOUT', '10'))
    SEARXNG_MAX_RESULTS = int(os.environ.get('MIROSHARK_SEARXNG_MAX_RESULTS', '5'))

    # Firecrawl-for-agents — when set, URL document ingestion scrapes pages
    # directly (POST /v1/scrape → markdown) instead of asking the websearch
    # LLM to read them. Falls back to WEB_SEARCH_MODEL when unset or on failure.
    FIRECRAWL_BASE_URL = (os.environ.get('MIROSHARK_FIRECRAWL_BASE_URL', '') or '').strip().rstrip('/')
    FIRECRAWL_API_KEY = os.environ.get('MIROSHARK_FIRECRAWL_API_KEY', '')

    # Wonderwall model — model for Wonderwall/CAMEL agent simulation loop.
    # Defaults to deepseek/deepseek-v4-flash:nitro; set WONDERWALL_MODEL_NAME=
    # (empty) to inherit LLM_MODEL_NAME.
    # Wonderwall is the #1 cost driver — 850+ calls per run. Keep it cheap.
    WONDERWALL_MODEL_NAME = os.environ.get('WONDERWALL_MODEL_NAME', 'deepseek/deepseek-v4-flash:nitro')
    # Optional per-slot endpoint override — point Wonderwall at a different
    # OpenAI-compatible API (e.g. a self-hosted Modal/vLLM endpoint) without
    # affecting the Default/Smart/NER slots. When unset, the simulation
    # subprocess falls back to LLM_API_KEY / LLM_BASE_URL.
    WONDERWALL_API_KEY = os.environ.get('WONDERWALL_API_KEY', '')
    WONDERWALL_BASE_URL = os.environ.get('WONDERWALL_BASE_URL', '')

    # NER model — faster model for entity extraction (high-volume, mechanical task)
    # Defaults to google/gemini-3-flash-preview (stable JSON with reasoning disabled);
    # set NER_MODEL_NAME= (empty) to inherit the default LLM config above.
    NER_MODEL_NAME = os.environ.get('NER_MODEL_NAME', 'google/gemini-3-flash-preview')
    NER_BASE_URL = os.environ.get('NER_BASE_URL', '')
    NER_API_KEY = os.environ.get('NER_API_KEY', '')

    # Observability configuration
    MIROSHARK_LOG_PROMPTS = os.environ.get('MIROSHARK_LOG_PROMPTS', 'false').lower() == 'true'
    MIROSHARK_LOG_LEVEL = os.environ.get('MIROSHARK_LOG_LEVEL', 'info')  # debug|info|warn

    # Anthropic prompt caching — when true and the active model is a Claude
    # variant, LLMClient attaches cache_control:{"type":"ephemeral"} to the
    # system message so repeated calls with the same prefix pay ~10% on cache
    # reads. Biggest wins: report ReACT loop (~N iterations per section × M
    # sections, all with the same system prompt) and graph-building NER.
    # Silently no-ops for non-Anthropic models.
    LLM_PROMPT_CACHING_ENABLED = os.environ.get('LLM_PROMPT_CACHING_ENABLED', 'true').lower() == 'true'

    # Extra token budget added transparently to every API call for thinking/reasoning
    # models (e.g. deepseek-v4-flash, Qwen3) whose <think> blocks consume tokens
    # from the same max_tokens pool as the actual response. Callers continue to
    # specify only their response budget; LLMClient adds this value so both fit.
    # 0 = safe default for non-thinking models (no change in behaviour).
    THINKING_BUDGET_TOKENS = int(os.environ.get('THINKING_BUDGET_TOKENS', '0'))

    # Disable chain-of-thought on reasoning-capable OpenRouter models by default.
    # Passes `reasoning: {enabled: false}` in extra_body — huge latency win
    # (~3x on Qwen3-Flash, ~3x on Gemini-3-Flash) and zero-op on models that
    # ignore the flag. Set false if a slot benefits from CoT (rare for
    # MiroShark's short, structured prompts).
    LLM_DISABLE_REASONING = os.environ.get('LLM_DISABLE_REASONING', 'true').lower() == 'true'

    # Report Agent configuration
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    # Outbound webhook fired when a simulation reaches a terminal state.
    # When set, MiroShark POSTs a JSON summary (scenario, final consensus,
    # quality, share URL, …) to this URL the moment the run completes or
    # fails. Slot for Zapier / Make / n8n / IFTTT / Slack Incoming Webhooks
    # / Discord channel webhooks / custom listeners — no bot, no OAuth.
    # Empty string disables it entirely. Editable at runtime via the
    # Settings modal — see app/services/webhook_service.py.
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')

    # Public base URL of this deployment (e.g. ``https://miroshark.app``).
    # When set, the outbound webhook payload includes absolute
    # ``share_url`` + ``share_card_url`` fields so Slack / Discord
    # consumers get rich unfurling out of the box. Without it, only the
    # relative ``share_path`` is included and the consumer must build the
    # absolute URL themselves.
    PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', '')

    # OriginTrail DKG (Decentralized Knowledge Graph) publishing.
    # Optional integration that anchors a finished simulation's
    # citation surface (scenario, agent count, final consensus, quality,
    # lineage, reproduce.json hash) on the OriginTrail DKG as a
    # cryptographically verifiable Knowledge Asset. The returned UAL +
    # Merkle root + transaction hash become a permanent, blockchain-anchored
    # citation key — same provenance property Stripe / DOI give a record,
    # but for simulation results.
    #
    # All four vars empty → integration disabled, ``/api/config/notifications``
    # reports ``dkg_configured: false``, the EmbedDialog hides the button.
    # Operator runs the OriginTrail daemon locally (``dkg init && dkg
    # start``) on the testnet faucet path, creates a context graph
    # (``dkg context-graph create miroshark``), pastes the auth token + CG
    # id here. ``DKG_NETWORK`` is metadata only — labels the chain the
    # daemon was configured against so the explorer URL is correct.
    DKG_API_URL = os.environ.get('DKG_API_URL', '').rstrip('/')
    DKG_AUTH_TOKEN = os.environ.get('DKG_AUTH_TOKEN', '')
    DKG_CONTEXT_GRAPH_ID = os.environ.get('DKG_CONTEXT_GRAPH_ID', '')
    DKG_NETWORK = (os.environ.get('DKG_NETWORK', 'testnet') or 'testnet').strip().lower()

    # WaybackClaw AI Agent Archive publishing.
    # Optional integration that submits a finished simulation's snapshot
    # (scenario, agent count, consensus, quality, lineage, reproduce.json
    # hash) to the WaybackClaw archive at ``api.waybackclaw.space``. The
    # archive pins every snapshot to IPFS and broadcasts a NIP-01 note to
    # Nostr relays, so a submission yields a content-addressed IPFS CID +
    # a censorship-resistant Nostr event id alongside the archive's
    # internal snapshot id. The pair is the agent-archive sibling of the
    # OriginTrail DKG citation surface.
    #
    # Required:
    #   * ``WAYBACKCLAW_AGENT_TOKEN`` — agent token issued by
    #     ``POST /api/archive/register``. Format: ``agent_<id>:<secret>``.
    #     Empty → integration disabled, ``/api/config/notifications``
    #     reports ``waybackclaw_configured: false``, the EmbedDialog
    #     hides the card.
    # Optional:
    #   * ``WAYBACKCLAW_API_URL`` — override the API endpoint (defaults
    #     to ``https://api.waybackclaw.space``). Useful for staging
    #     deployments or a self-hosted fork.
    #   * ``WAYBACKCLAW_AGENT_CATEGORY`` — WaybackClaw taxonomy slot
    #     for this deployment's snapshots (defaults to ``prediction``,
    #     which fits a multi-agent swarm running prediction-market-style
    #     consensus runs).
    WAYBACKCLAW_API_URL = os.environ.get('WAYBACKCLAW_API_URL', '').rstrip('/')
    WAYBACKCLAW_AGENT_TOKEN = os.environ.get('WAYBACKCLAW_AGENT_TOKEN', '')
    WAYBACKCLAW_AGENT_CATEGORY = (
        os.environ.get('WAYBACKCLAW_AGENT_CATEGORY', '') or ''
    ).strip().lower()

    # Demographic grounding — optional Nemotron-anchored persona generation.
    # When ``DEMOGRAPHICS_COUNTRY`` matches an entry under
    # ``backend/app/countries/`` (e.g. ``sg`` or ``us``), the persona
    # generator pulls one census-grounded row per entity from the
    # corresponding NVIDIA Nemotron-Personas parquet dataset and feeds it
    # to the LLM as a demographic anchor — age, sex, geography, occupation,
    # education, industry. Falls back to graph-only generation when:
    #   * the env var is empty,
    #   * the country code is unknown,
    #   * ``duckdb`` / ``huggingface_hub`` aren't installed, or
    #   * neither a local parquet glob nor an HF snapshot is reachable.
    # The feature is purely additive: agents that don't get a seed still
    # generate normally, so partial coverage degrades cleanly.
    DEMOGRAPHICS_COUNTRY = (os.environ.get('DEMOGRAPHICS_COUNTRY', '') or '').strip().lower()

    # Whether ``GET /sitemap.xml`` is served and ``robots.txt`` advertises
    # it. Default ``true`` — the public sitemap is the search-engine
    # discovery surface for the public-simulation gallery, and a
    # crawl-ready sitemap is the right default for any deployment that
    # exposes ``/share/<id>`` URLs publicly. Operators running a private
    # MiroShark instance set ``ENABLE_SITEMAP=false`` to make the sitemap
    # 404 and drop the ``Sitemap:`` directive from robots.txt.
    ENABLE_SITEMAP = os.environ.get('ENABLE_SITEMAP', 'true').lower() == 'true'

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []
        if cls.LLM_PROVIDER != 'claude-code' and not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY is not configured")
        if not cls.NEO4J_URI:
            errors.append("NEO4J_URI is not configured")
        if not cls.NEO4J_PASSWORD:
            errors.append("NEO4J_PASSWORD is not configured")
        if cls.THINKING_BUDGET_TOKENS > 0 and cls.LLM_DISABLE_REASONING:
            import warnings
            warnings.warn(
                "THINKING_BUDGET_TOKENS is set but LLM_DISABLE_REASONING=true (default) "
                "will suppress <think> blocks via reasoning:{enabled:false} — the extra "
                "token budget is wasted. Set LLM_DISABLE_REASONING=false to use thinking "
                "models, or remove THINKING_BUDGET_TOKENS for non-thinking models.",
                stacklevel=2,
            )
        return errors

