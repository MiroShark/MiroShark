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
    # Cheap preset: qwen/qwen3.5-flash-02-23 (with LLM_DISABLE_REASONING=true)
    # Best preset:  anthropic/claude-haiku-4.5 (rich personas, dense sim configs)
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'openai')
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'qwen/qwen3.5-flash-02-23')

    # Smart model — stronger model for intelligence-sensitive workflows
    # (report generation, ontology extraction, graph reasoning).
    # When not set, these workflows use the default LLM config above.
    # Cheap preset: deepseek/deepseek-v3.2 (non-reasoning, stable JSON)
    # Best preset:  anthropic/claude-sonnet-4.6 (9/10 report quality)
    SMART_PROVIDER = os.environ.get('SMART_PROVIDER', '')   # "openai", "claude-code", or empty (inherit)
    SMART_API_KEY = os.environ.get('SMART_API_KEY', '')
    SMART_BASE_URL = os.environ.get('SMART_BASE_URL', '')
    SMART_MODEL_NAME = os.environ.get('SMART_MODEL_NAME', '')
    
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
    # Optional: dedicated model for web research (e.g. "perplexity/sonar-pro" on OpenRouter
    # for grounded search, or "perplexity/sonar" for fast search). If empty, uses default LLM.
    WEB_SEARCH_MODEL = os.environ.get('WEB_SEARCH_MODEL', '')

    # Wonderwall model — model for Wonderwall/CAMEL agent simulation loop.
    # When not set, uses LLM_MODEL_NAME.
    # Cheap preset: qwen/qwen3.5-flash-02-23 (same as default to reuse quota)
    # Wonderwall is the #1 cost driver — 850+ calls per run. Keep it cheap.
    WONDERWALL_MODEL_NAME = os.environ.get('WONDERWALL_MODEL_NAME', '')

    # NER model — faster model for entity extraction (high-volume, mechanical task)
    # When not set, NER uses the default LLM config above.
    # Cheap preset: x-ai/grok-4.1-fast (stable JSON with reasoning disabled)
    NER_MODEL_NAME = os.environ.get('NER_MODEL_NAME', '')
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

    # Disable chain-of-thought on reasoning-capable OpenRouter models by default.
    # Passes `reasoning: {enabled: false}` in extra_body — huge latency win
    # (~3x on Qwen3-Flash, ~3x on Grok-4.1-Fast) and zero-op on models that
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
        return errors

