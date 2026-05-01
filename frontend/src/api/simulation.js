import service, { requestWithRetry } from './index'

/**
 * Create simulation
 * @param {Object} data - { project_id, graph_id?, enable_twitter?, enable_reddit?, enable_polymarket? }
 */
export const createSimulation = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/create', data), 3, 1000)
}

/**
 * Prepare simulation environment (async task)
 * @param {Object} data - { simulation_id, entity_types?, use_llm_for_profiles?, parallel_profile_count?, force_regenerate? }
 */
export const prepareSimulation = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/prepare', data), 3, 1000)
}

/**
 * Query preparation task progress
 * @param {Object} data - { task_id?, simulation_id? }
 */
export const getPrepareStatus = (data) => {
  return service.post('/api/simulation/prepare/status', data)
}

/**
 * Get simulation status
 * @param {string} simulationId
 */
export const getSimulation = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}`)
}

/**
 * Get simulation Agent Profiles
 * @param {string} simulationId
 * @param {string} platform - 'reddit' | 'twitter'
 */
export const getSimulationProfiles = (simulationId, platform = 'reddit') => {
  return service.get(`/api/simulation/${simulationId}/profiles`, { params: { platform } })
}

/**
 * Get Agent Profiles being generated in real-time
 * @param {string} simulationId
 * @param {string} platform - 'reddit' | 'twitter'
 */
export const getSimulationProfilesRealtime = (simulationId, platform = 'reddit') => {
  return service.get(`/api/simulation/${simulationId}/profiles/realtime`, { params: { platform } })
}

/**
 * Get simulation configuration
 * @param {string} simulationId
 */
export const getSimulationConfig = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/config`)
}

/**
 * Get simulation configuration being generated in real-time
 * @param {string} simulationId
 * @returns {Promise} Returns configuration info, including metadata and config content
 */
export const getSimulationConfigRealtime = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/config/realtime`)
}

/**
 * Retry config generation (profiles must already exist)
 * @param {string} simulationId
 */
export const retrySimulationConfig = (simulationId) => {
  return requestWithRetry(() => service.post(`/api/simulation/${simulationId}/config/retry`), 2, 1000)
}

/**
 * List all simulations
 * @param {string} projectId - Optional, filter by project ID
 */
export const listSimulations = (projectId) => {
  const params = projectId ? { project_id: projectId } : {}
  return service.get('/api/simulation/list', { params })
}

/**
 * Start simulation
 * @param {Object} data - { simulation_id, platform?, max_rounds?, enable_graph_memory_update?, enable_cross_platform? }
 */
export const startSimulation = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/start', data), 3, 1000)
}

/**
 * Stop simulation
 * @param {Object} data - { simulation_id }
 */
export const stopSimulation = (data) => {
  return service.post('/api/simulation/stop', data)
}

/**
 * Resume simulation from last completed round
 * @param {Object} data - { simulation_id, platform?, enable_graph_memory_update? }
 */
export const resumeSimulation = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/start', {
    ...data,
    resume: true,
    force: true  // force past status checks since previous run failed/stopped
  }), 3, 1000)
}

/**
 * Get simulation run real-time status
 * @param {string} simulationId
 */
export const getRunStatus = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/run-status`)
}

/**
 * Get simulation run detailed status (including recent actions)
 * @param {string} simulationId
 */
export const getRunStatusDetail = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/run-status/detail`)
}

/**
 * Compare two simulations side by side
 * @param {string} id1 - First simulation ID
 * @param {string} id2 - Second simulation ID
 */
export const compareSimulations = (id1, id2) => {
  return service.get('/api/simulation/compare', { params: { id1, id2 } })
}

/**
 * Get posts in simulation
 * @param {string} simulationId
 * @param {string} platform - 'reddit' | 'twitter'
 * @param {number} limit - Number of results to return
 * @param {number} offset - Offset
 */
export const getSimulationPosts = (simulationId, platform = 'reddit', limit = 50, offset = 0) => {
  return service.get(`/api/simulation/${simulationId}/posts`, {
    params: { platform, limit, offset }
  })
}

/**
 * Get simulation timeline (summarized by round)
 * @param {string} simulationId
 * @param {number} startRound - Starting round
 * @param {number} endRound - Ending round
 */
export const getSimulationTimeline = (simulationId, startRound = 0, endRound = null) => {
  const params = { start_round: startRound }
  if (endRound !== null) {
    params.end_round = endRound
  }
  return service.get(`/api/simulation/${simulationId}/timeline`, { params })
}

/**
 * Get Agent statistics
 * @param {string} simulationId
 */
export const getAgentStats = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/agent-stats`)
}

/**
 * Get simulation action history
 * @param {string} simulationId
 * @param {Object} params - { limit, offset, platform, agent_id, round_num }
 */
export const getSimulationActions = (simulationId, params = {}) => {
  return service.get(`/api/simulation/${simulationId}/actions`, { params })
}

/**
 * Restart simulation environment for interviews (without running simulation)
 * @param {Object} data - { simulation_id }
 */
export const restartEnv = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/restart-env', data), 3, 1000)
}

/**
 * Close simulation environment (graceful shutdown)
 * @param {Object} data - { simulation_id, timeout? }
 */
export const closeSimulationEnv = (data) => {
  return service.post('/api/simulation/close-env', data)
}

/**
 * Get simulation environment status
 * @param {Object} data - { simulation_id }
 */
export const getEnvStatus = (data) => {
  return service.post('/api/simulation/env-status', data)
}

/**
 * Export simulation data as JSON or CSV file download
 * @param {string} simulationId
 * @param {string} format - 'json' or 'csv'
 */
export const exportSimulationData = (simulationId, format = 'json') => {
  return service.get(`/api/simulation/${simulationId}/export`, {
    params: { format },
    responseType: 'blob'
  })
}

/**
 * Batch interview Agents
 * @param {Object} data - { simulation_id, interviews: [{ agent_id, prompt }] }
 */
export const interviewAgents = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/interview/batch', data), 3, 1000)
}

/**
 * Get historical simulation list (with project details)
 * Used for homepage historical project display
 * @param {number} limit - Result count limit
 */
export const getSimulationHistory = (limit = 20) => {
  return service.get('/api/simulation/history', { params: { limit } })
}

/**
 * Get agent influence leaderboard for a completed simulation
 * @param {string} simulationId
 * @returns {Promise<{agents: Array, total_agents: number}>}
 */
export const getInfluenceLeaderboard = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/influence`)
}

/**
 * Get per-round belief drift distribution (bullish/neutral/bearish agent percentages)
 * @param {string} simulationId
 * @returns {Promise<{rounds, bullish, neutral, bearish, topics, consensus_round, summary}>}
 */
export const getBeliefDrift = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/belief-drift`)
}

/**
 * Recompute belief drift excluding a subset of agents ("What If?" analysis).
 * Pure data transform — no re-simulation, returns both original and
 * counterfactual drift curves plus headline deltas.
 * @param {string} simulationId
 * @param {string[]} excludeAgents - agent usernames to remove from analysis
 */
export const getCounterfactualDrift = (simulationId, excludeAgents = []) => {
  const params = {}
  if (excludeAgents && excludeAgents.length) {
    params.exclude_agents = excludeAgents.join(',')
  }
  return service.get(`/api/simulation/${simulationId}/counterfactual`, { params })
}

/**
 * Fork a simulation — copies agent profiles and config into a new simulation
 * that is immediately ready to run.
 * @param {Object} data - { parent_simulation_id, simulation_requirement? }
 */
export const forkSimulation = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/fork', data), 3, 1000)
}

/**
 * Record the real-world outcome of a simulation prediction.
 * @param {string} simulationId
 * @param {Object} data - { actual_outcome: 'YES' | 'NO', notes?: string }
 */
export const resolveSimulation = (simulationId, data) => {
  return service.post(`/api/simulation/${simulationId}/resolve`, data)
}

/**
 * Generate a publishable article brief from simulation results (cached).
 * @param {string} simulationId
 * @param {Object} options - { force_regenerate?, share_url? }
 */
export const generateSimulationArticle = (simulationId, options = {}) => {
  return service.post(`/api/simulation/${simulationId}/article`, options)
}

/**
 * Post-simulation trace-grounded agent interview.
 * Works on completed simulations without needing the env running.
 * @param {string} simulationId
 * @param {string} agentName
 * @param {Object} data - { question: string, history?: [{role, content}] }
 */
export const traceInterviewAgent = (simulationId, agentName, data) => {
  return service.post(
    `/api/simulation/${simulationId}/agents/${encodeURIComponent(agentName)}/trace-interview`,
    data
  )
}

/**
 * Get saved interview transcript for an agent.
 * @param {string} simulationId
 * @param {string} agentName
 */
export const getAgentInterview = (simulationId, agentName) => {
  return service.get(
    `/api/simulation/${simulationId}/interviews/${encodeURIComponent(agentName)}`
  )
}

/**
 * Get the VAPID public key for Web Push subscriptions.
 * Returns { data: { public_key: string | null } }
 */
export const getVapidPublicKey = () => {
  return service.get('/api/simulation/push/vapid-public-key')
}

/**
 * Store a Web Push subscription for a simulation.
 * @param {Object} data - { simulation_id, subscription }
 */
export const subscribePush = (data) => {
  return service.post('/api/simulation/push/subscribe', data)
}

/**
 * Fire a test push notification immediately (for debugging).
 * @param {string} simulationId
 */
export const testPushNotification = (simulationId) => {
  return service.post('/api/simulation/push/test', { simulation_id: simulationId })
}

/**
 * Get agent interaction network graph data for a completed simulation.
 * @param {string} simulationId
 * @returns {Promise<{nodes: Array, edges: Array, insights: Object}>}
 */
export const getInteractionNetwork = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/interaction-network`)
}

/**
 * Inject a breaking event into a running simulation (Director Mode).
 * @param {string} simulationId
 * @param {Object} data - { event_text: string }
 */
export const injectDirectorEvent = (simulationId, data) => {
  return service.post(`/api/simulation/${simulationId}/director/inject`, data)
}

/**
 * Get all director events (injected + pending) for a simulation.
 * @param {string} simulationId
 */
export const getDirectorEvents = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/director/events`)
}

/**
 * Get quality diagnostics for a completed simulation.
 * @param {string} simulationId
 * @returns {Promise<{participation_rate, stance_entropy, convergence_round, cross_platform_rate, health, suggestions}>}
 */
export const getSimulationQuality = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/quality`)
}

/**
 * Get a minimal summary for rendering the embeddable widget.
 * @param {string} simulationId
 * @returns {Promise<{simulation_id, scenario, status, current_round, total_rounds, profiles_count, belief, quality, resolution}>}
 */
export const getEmbedSummary = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/embed-summary`)
}

/**
 * Publish or unpublish a simulation so the embed-summary endpoint returns
 * 200 vs 403. Defaults to publishing; pass {public:false} to unpublish.
 * @param {string} simulationId
 * @param {boolean} publicFlag
 */
export const publishSimulation = (simulationId, publicFlag = true) => {
  return service.post(`/api/simulation/${simulationId}/publish`, { public: publicFlag })
}

/**
 * Build the absolute URL of the 1200x630 PNG share card for a simulation.
 *
 * The card is server-rendered from the same data that powers the embed
 * widget — scenario, status, agent count, belief drift split, quality
 * health, resolution. Requires the simulation to be published (same gate
 * as the embed widget).
 *
 * Returns an absolute URL (rather than fetching) so it can be dropped
 * straight into an `<img src>` for previews or copied to the clipboard
 * for manual pasting into Twitter/X / Discord / Slack.
 *
 * @param {string} simulationId
 * @param {string} [origin] - override base URL (defaults to window.location.origin)
 * @returns {string}
 */
export const getShareCardUrl = (simulationId, origin) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}/api/simulation/${simulationId}/share-card.png`
}

/**
 * Build the absolute URL of the animated belief-replay GIF for a simulation.
 *
 * 1200×630 (matches the share card aspect ratio). One frame per round
 * with belief bars sliding to that round's bullish/neutral/bearish
 * split. Discord and Slack auto-play GIFs from direct file URLs, so
 * pasting this link drops a motion preview into the channel.
 *
 * Same publish gate as the share card. Returns the absolute URL only —
 * the caller is expected to drop it into an `<img src>` or a download
 * `<a href>` rather than fetching the bytes itself.
 *
 * @param {string} simulationId
 * @param {string} [origin] - override base URL (defaults to window.location.origin)
 * @returns {string}
 */
export const getReplayGifUrl = (simulationId, origin) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}/api/simulation/${simulationId}/replay.gif`
}

/**
 * Build the absolute URL of the Markdown transcript export for a
 * simulation. The transcript is the text companion to the share card
 * (preview) and replay GIF (motion) — per-round agent posts + stances
 * + final consensus, with YAML front matter so Notion / Obsidian /
 * Bear pick it up as page metadata.
 *
 * Same publish gate as the share card. Returns the absolute URL only —
 * callers drop it into a download `<a href>` or copy it for manual use.
 *
 * @param {string} simulationId
 * @param {string} [origin]
 * @returns {string}
 */
export const getTranscriptMarkdownUrl = (simulationId, origin) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}/api/simulation/${simulationId}/transcript.md`
}

/**
 * Build the absolute URL of the JSON transcript export — same payload
 * as the Markdown form but in a structured shape for SDKs / downstream
 * pipelines (LLM-as-judge evals, Python client SDK consumers, etc.).
 *
 * @param {string} simulationId
 * @param {string} [origin]
 * @returns {string}
 */
export const getTranscriptJsonUrl = (simulationId, origin) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}/api/simulation/${simulationId}/transcript.json`
}

/**
 * Build the absolute URL of the per-round belief trajectory CSV
 * export. One row per recorded round with bullish / neutral / bearish
 * percent (same ±0.2 stance threshold as every other surface),
 * participating agents, post + engagement counts, and quality health.
 *
 * Intended for `pandas.read_csv()` / Excel / Tableau / R / Observable
 * — the analyst's default toolkit. Same publish gate as the share
 * card and transcript.
 *
 * @param {string} simulationId
 * @param {string} [origin]
 * @returns {string}
 */
export const getTrajectoryCsvUrl = (simulationId, origin) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}/api/simulation/${simulationId}/trajectory.csv`
}

/**
 * Build the absolute URL of the per-round belief trajectory JSONL
 * (newline-delimited JSON) export — same row shape as the CSV form
 * but as one JSON object per line. The format `pandas.read_json(lines=true)`,
 * DuckDB `read_json_auto`, and stream-processing pipelines consume
 * natively without a CSV-to-DataFrame conversion.
 *
 * @param {string} simulationId
 * @param {string} [origin]
 * @returns {string}
 */
export const getTrajectoryJsonlUrl = (simulationId, origin) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}/api/simulation/${simulationId}/trajectory.jsonl`
}

/**
 * Build the absolute URL of the public share landing page for a
 * simulation. The page exposes Open Graph + Twitter Card meta tags so
 * pasting the URL into Twitter/X / Discord / Slack / LinkedIn unfurls
 * with the share card image, scenario as title, etc. Real browsers are
 * redirected to the SPA simulation view instantly.
 *
 * @param {string} simulationId
 * @param {string} [origin]
 * @returns {string}
 */
export const getShareLandingUrl = (simulationId, origin) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}/share/${simulationId}`
}

/**
 * Build the absolute URL of the public-gallery syndication feed.
 *
 * Atom 1.0 by default — the format browsers auto-discover and modern
 * readers prefer. Pass `format: 'rss'` for the RSS 2.0 variant. When
 * `verified` is truthy the feed is restricted to simulations with a
 * recorded outcome annotation (the `/verified` curated hall).
 *
 * The endpoint is publish-gated: every entry is a simulation already
 * visible on /explore, so subscribing maps 1:1 to "every new public
 * MiroShark simulation lands in my reader."
 *
 * @param {Object} [options]
 * @param {('atom'|'rss')} [options.format='atom']
 * @param {boolean} [options.verified=false]
 * @param {string} [options.origin]
 * @returns {string}
 */
export const getFeedUrl = ({ format = 'atom', verified = false, origin } = {}) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  const ext = format === 'rss' ? 'rss' : 'atom'
  const query = verified ? '?verified=1' : ''
  return `${base}/api/feed.${ext}${query}`
}

/**
 * Branch a simulation with a narrative injection at a specific round.
 * The new simulation is READY and shares the parent's agent population;
 * when the runner hits trigger_round it auto-promotes the injection into
 * a director event so agents see "breaking news" starting that round.
 *
 * @param {string} parentSimulationId
 * @param {{ injectionText: string, triggerRound: number, label?: string, branchId?: string }} opts
 */
export const branchCounterfactual = (parentSimulationId, opts) => {
  return service.post('/api/simulation/branch-counterfactual', {
    parent_simulation_id: parentSimulationId,
    injection_text: opts.injectionText,
    trigger_round: opts.triggerRound,
    label: opts.label,
    branch_id: opts.branchId,
  })
}

/**
 * Get a single round's snapshot — actions in the round, market prices at
 * that round, and belief state. Lightweight alternative to
 * getRunStatusDetail for scrubbing UIs on large simulations.
 * @param {string} simulationId
 * @param {number} roundNum
 * @param {{ platforms?: string[], includeBelief?: boolean, includeMarket?: boolean }} opts
 */
export const getSimulationFrame = (simulationId, roundNum, opts = {}) => {
  const params = {}
  if (opts.platforms && opts.platforms.length) params.platforms = opts.platforms.join(',')
  if (opts.includeBelief === false) params.include_belief = 'false'
  if (opts.includeMarket === false) params.include_market = 'false'
  return service.get(`/api/simulation/${simulationId}/frame/${roundNum}`, { params })
}

/**
 * Ask mode: turn a single question into a synthesized seed document +
 * simulation_requirement. The result plugs directly into
 * /api/graph/ontology/generate as a url_docs entry, so the downstream pipeline
 * (ontology, graph build, profiles, sim) is unchanged.
 * @param {string} question
 * @param {{ noCache?: boolean }} opts
 */
export const askMode = (question, opts = {}) => {
  return service.post('/api/simulation/ask', {
    question,
    no_cache: !!opts.noCache,
  })
}

/**
 * Get demographic breakdown (age / gender / country / archetype / primary
 * platform) cross-tabbed against final stance, stance volatility, and
 * influence.
 * @param {string} simulationId
 * @param {Object} options - { refresh?: boolean }
 */
export const getDemographicBreakdown = (simulationId, options = {}) => {
  const params = options.refresh ? { refresh: 'true' } : {}
  return service.get(`/api/simulation/${simulationId}/demographics`, { params })
}

/**
 * Fetch the most recent items across configured RSS/Atom feeds. Used by the
 * Home screen "What's Trending" panel — gives users who arrive without a
 * specific document a one-click starting point. Clicking a card pre-fills
 * the URL field and immediately fires the existing fetch + scenario-suggest
 * pipeline.
 *
 * Response shape:
 *   {
 *     items: [
 *       { title, url, source_name, published_at }
 *     ],
 *     feeds_used: [...],
 *     cached: boolean,
 *     fetched_at?: string,
 *     reason?: 'rate_limited' | 'no_feeds_configured' | 'internal_error'
 *   }
 *
 * An empty `items` array is normal when every feed errored — the caller
 * should hide the panel silently.
 *
 * @param {Object} options - { feeds?: string[], refresh?: boolean }
 */
export const getTrendingTopics = (options = {}) => {
  const params = {}
  if (Array.isArray(options.feeds) && options.feeds.length) {
    params.feeds = options.feeds.join(',')
  }
  if (options.refresh) params.refresh = 'true'
  return service.get('/api/simulation/trending', { params, timeout: 12000 })
}

/**
 * Generate 3 prediction-market-style scenario suggestions from a document
 * preview. Used by the Home screen to eliminate the blank-page problem at
 * simulation setup — the user pastes a URL or drops a file, and within a
 * couple of seconds three scenario cards appear.
 *
 * Response shape (best-effort):
 *   {
 *     suggestions: [
 *       { question, label: 'Bull'|'Bear'|'Neutral',
 *         expected_yes_range: [lo, hi], rationale }
 *     ],
 *     cached: boolean,
 *     model: string | null,
 *     reason?: 'preview_too_short' | 'llm_unavailable' | 'llm_error'
 *   }
 *
 * An empty `suggestions` array (with a `reason`) is normal — the caller should
 * simply not render the panel.
 *
 * @param {Object} data - { text_preview: string, no_cache?: boolean }
 */
export const suggestScenarios = (data) => {
  return service.post('/api/simulation/suggest-scenarios', data, { timeout: 25000 })
}

/**
 * List simulations that have been toggled public via the /publish endpoint.
 * Powers the /explore gallery — every entry already has a rendered share
 * card, embed summary, and public landing page, so the frontend just
 * needs to lay them out.
 *
 * Response shape:
 *   {
 *     data: [
 *       { simulation_id, scenario, status, runner_status, current_round,
 *         total_rounds, agent_count, quality_health, final_consensus,
 *         resolution_outcome, outcome, created_at, parent_simulation_id,
 *         share_card_url, share_landing_url }
 *     ],
 *     count: number,        // items on this page
 *     total: number,        // total public simulations
 *     limit: number,
 *     offset: number,
 *     has_more: boolean,
 *     verified_only: boolean
 *   }
 *
 * An empty `data` array is normal (render the empty state).
 * @param {Object} options - { limit?: number, offset?: number, verifiedOnly?: boolean }
 */
export const getPublicSimulations = (options = {}) => {
  const params = {}
  if (Number.isFinite(options.limit)) params.limit = options.limit
  if (Number.isFinite(options.offset)) params.offset = options.offset
  if (options.verifiedOnly) params.verified = '1'
  return service.get('/api/simulation/public', { params, timeout: 15000 })
}

/**
 * Read the verified-prediction annotation for a simulation.
 * Returns `data: null` when none has been submitted yet.
 * @param {string} simulationId
 */
export const getSimulationOutcome = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/outcome`)
}

/**
 * Record a verified-prediction annotation for a public simulation.
 * Submitting again overwrites the previous annotation. Requires the
 * simulation to be public.
 * @param {string} simulationId
 * @param {Object} data - { label: 'correct' | 'incorrect' | 'partial', outcome_url?: string, outcome_summary?: string }
 */
export const submitSimulationOutcome = (simulationId, data) => {
  return service.post(`/api/simulation/${simulationId}/outcome`, data)
}

/**
 * List all Polymarket prediction markets for a simulation.
 * @param {string} simulationId
 */
export const getPolymarketMarkets = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/polymarket/markets`)
}

/**
 * Time-series of YES price for a single market, reconstructed from trades.
 * @param {string} simulationId
 * @param {number} marketId
 */
export const getPolymarketMarketPrices = (simulationId, marketId) => {
  return service.get(`/api/simulation/${simulationId}/polymarket/market/${marketId}/prices`)
}

