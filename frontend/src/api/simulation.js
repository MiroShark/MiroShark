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
 * Build the absolute URL of the per-round belief trajectory chart
 * rendered as a stdlib-pure SVG. Scalable-vector companion to the
 * share card (PNG verdict), replay GIF (motion), and Jupyter
 * notebook (matplotlib). Three lines — bullish / neutral / bearish —
 * plotted against round number on a 800×400 viewBox.
 *
 * Embeddable as `<img src="…/chart.svg">` in Notion, Substack, Ghost,
 * GitHub READMEs, and LaTeX — vector means no resolution choice, and
 * `<img>` means no JavaScript at the embed site.
 *
 * @param {string} simulationId
 * @param {string} [origin]
 * @returns {string}
 */
export const getChartSvgUrl = (simulationId, origin) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}/api/simulation/${simulationId}/chart.svg`
}

/**
 * Fetch the Farcaster Frame v2 metadata for a published simulation.
 *
 * $MIROSHARK lives on Base; the Base-native social network is Farcaster
 * / Warpcast. A `/share/<id>` URL pasted into a Farcaster cast renders
 * as an interactive Frame card — chart-SVG image as the preview, a
 * "View Simulation →" link button — once the share-page emits the
 * matching `fc:frame:*` meta tags. The EmbedDialog calls this endpoint
 * to build the Warpcast compose link without hardcoding the host, and
 * to surface the Frame image / button details for the operator.
 *
 * Returns `{ success, data }` where `data` contains `frame_version`,
 * `image_url`, `image_aspect_ratio`, `share_url`, `buttons`,
 * `has_trajectory`. Returns `{ success: false, ... }` (HTTP 403) for
 * unpublished sims and `404` for unknown sim ids — both cases are
 * treated as "no Frame preview" by the dialog.
 *
 * @param {string} simulationId
 * @returns {Promise<object>}
 */
export const getFrameMetadata = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/frame-metadata`)
}

/**
 * Build a Warpcast composer URL pre-filled with the share link so the
 * operator lands inside the Warpcast composer with the Frame card
 * already attached. Same URL-encoding scheme the backend
 * `frame_metadata.warpcast_compose_url` helper uses — kept in sync
 * with the backend so the test surface is one truth.
 *
 * @param {string} shareUrl
 * @returns {string}
 */
export const buildWarpcastComposeUrl = (shareUrl) => {
  if (!shareUrl) return 'https://warpcast.com/~/compose'
  return `https://warpcast.com/~/compose?embeds[]=${encodeURIComponent(shareUrl)}`
}

/**
 * Build the absolute URL of the machine-readable trading signal for a
 * published simulation. Collapses the final-round belief split + quality
 * health into a single action primitive a quant tool, alert pipeline,
 * or Zapier / Make / n8n workflow can consume directly.
 *
 * Returns a v1-schema JSON document with `direction` (Bullish / Neutral
 * / Bearish), `confidence_pct` (0 = pure three-way split, 100 =
 * unanimous), `risk_tier` (low / medium / high, mapped from quality
 * health), and the three component percentages.
 *
 * Same publish gate as every other share surface. Returns 404 when the
 * simulation hasn't recorded any rounds yet.
 *
 * @param {string} simulationId
 * @param {string} [origin]
 * @returns {string}
 */
export const getSignalJsonUrl = (simulationId, origin) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}/api/simulation/${simulationId}/signal.json`
}

/**
 * Fetch the trading-signal payload for a published simulation.
 *
 * Returns the parsed JSON document on 200, `null` on 404 (sim not
 * ready — no `belief.final` yet) or 403 (sim not published), and
 * throws on transport errors.
 *
 * @param {string} simulationId
 * @returns {Promise<object|null>}
 */
export const getSignalJson = async (simulationId) => {
  const res = await fetch(getSignalJsonUrl(simulationId), {
    credentials: 'omit',
    cache: 'no-store',
  })
  if (res.status === 403 || res.status === 404) {
    return null
  }
  if (!res.ok) {
    throw new Error(`signal.json fetch failed: ${res.status}`)
  }
  return res.json()
}

/**
 * Build the absolute URL of the auto-generated Twitter / X tweet
 * thread for a finished simulation. Plain-text form — one intro
 * tweet, one tweet per belief inflection point (rounds where the
 * dominant stance crossed the ±0.2 threshold), and one closing
 * tweet with the watch + share URLs. Tweets are separated by
 * `---` on its own line so an operator can copy individual ones.
 *
 * Pairs with the share card (preview), replay GIF (motion),
 * transcript (prose), and trajectory CSV/JSONL (data) as the
 * sixth share format — the short-form text channel X/Twitter
 * speaks natively.
 *
 * Same publish gate as the share card and transcript.
 *
 * @param {string} simulationId
 * @param {string} [origin]
 * @returns {string}
 */
export const getThreadTxtUrl = (simulationId, origin) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}/api/simulation/${simulationId}/thread.txt`
}

/**
 * Build the absolute URL of the JSON form of the same tweet thread
 * as `thread.txt`. Returns the structured payload — `tweets`,
 * `total`, `inflections_recorded`, `truncated` — so a programmatic
 * consumer (Twitter scheduling tool, Notion dashboard) can iterate
 * tweets without splitting on the `---` separator.
 *
 * @param {string} simulationId
 * @param {string} [origin]
 * @returns {string}
 */
export const getThreadJsonUrl = (simulationId, origin) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}/api/simulation/${simulationId}/thread.json`
}

/**
 * Fetch per-share-surface request counters for a published
 * simulation. Returns `{success, simulation_id, stats}` where `stats`
 * is the per-surface counter dict — `share_card`, `replay_gif`,
 * `transcript_md` / `transcript_json`, `trajectory_csv` /
 * `trajectory_jsonl`, `thread_txt` / `thread_json`, `watch_page`,
 * `feed_atom` / `feed_rss`, plus a synthetic `total`.
 *
 * The inbound observability surface — pairs with the outbound
 * webhook delivery log so an operator running MiroShark for a DeFi
 * fund or research group can see which surfaces their audience
 * actually uses.
 *
 * Same publish gate as the share card / transcript / trajectory /
 * thread endpoints. Returns 403 for unpublished simulations.
 *
 * @param {string} simulationId
 * @returns {Promise<{success: boolean, simulation_id: string, stats: object}>}
 */
export const getSurfaceStats = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/surface-stats`)
}

/**
 * Build the absolute URL of the reproducibility config blob for a
 * simulation.
 *
 * The blob is a v1-schema JSON document carrying every parameter
 * another operator would need to re-run the same simulation —
 * scenario text, agent count, total rounds, platform toggles, the
 * four cadence knobs from `time_config`, any operator-injected
 * director events, and a `lineage` block describing fork /
 * counterfactual parentage. The citation primitive behind every
 * other share surface.
 *
 * Same publish gate as the share card / transcript / trajectory /
 * thread endpoints. Returns 403 for unpublished simulations. Cached
 * for 5 minutes; identical exports of the same finished simulation
 * are bytewise-identical (citation-hash friendly).
 *
 * @param {string} simulationId
 * @param {string} [origin]
 * @returns {string}
 */
export const getReproductionUrl = (simulationId, origin) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}/api/simulation/${simulationId}/reproduce.json`
}

/**
 * Fetch the parsed reproducibility config blob for a published
 * simulation. Returns the same JSON document `getReproductionUrl`
 * resolves to, but as an in-memory object — useful for rendering the
 * lineage badge or the inline config preview without a second fetch.
 *
 * The endpoint follows the standard share-surface envelope: the
 * Flask handler returns the blob directly (not wrapped in
 * `{success, data}`), so callers consume `response.data` as the
 * blob itself.
 *
 * @param {string} simulationId
 * @returns {Promise<object>} the v1-schema reproduction blob
 */
export const getReproduction = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/reproduce.json`)
}

/**
 * Build the absolute URL of the pre-populated Jupyter notebook for a
 * published simulation.
 *
 * The notebook is an nbformat 4 `.ipynb` document with the trajectory
 * CSV embedded directly + scaffolded analysis cells (imports, CSV
 * load via `pd.read_csv(io.StringIO(...))`, belief-evolution line
 * chart, final consensus bar chart, quality + participation summary
 * DataFrame). Runs air-gapped — anyone with the file can hit Run All
 * without any network call back to the MiroShark host.
 *
 * Pairs with `trajectory.csv` as the second institution-targeted
 * export. The CSV told analysts "here is the data"; the notebook
 * tells them "here is the analysis, ready to run". Identical exports
 * of the same finished sim are bytewise-identical (citation-hash
 * friendly), same property the reproduce.json blob has.
 *
 * Same publish gate as the share card / transcript / trajectory /
 * thread / reproduce.json endpoints. Returns 403 for unpublished
 * simulations.
 *
 * @param {string} simulationId
 * @param {string} [origin]
 * @returns {string}
 */
export const getNotebookUrl = (simulationId, origin) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}/api/simulation/${simulationId}/notebook.ipynb`
}

/**
 * Fetch the lineage graph slice for a published simulation — the
 * parent it was forked / branched from (if any) and every public
 * child whose `parent_simulation_id` points back at it.
 *
 * Closes the navigation gap that PR #75's reproducibility config left
 * behind: the parent → children pointer existed on disk
 * (`parent_simulation_id` plus an optional
 * `counterfactual_injection.json`) but was one-directional, so a
 * researcher running counterfactual branches couldn't navigate from
 * a parent simulation to its branches without remembering each child
 * sim id.
 *
 * Same publish gate as the share card / transcript / trajectory /
 * thread / reproduce.json endpoints. Returns 403 for unpublished
 * simulations. Cached for 5 minutes — the graph slice is stable once
 * the parent and its branches reach terminal states.
 *
 * Response shape (under `data`):
 *   {
 *     simulation_id: string,
 *     lineage_kind: 'original' | 'fork' | 'counterfactual',
 *     parent: null | { simulation_id, scenario_preview, created_at, is_public },
 *     children: [
 *       { simulation_id, scenario_preview, created_at, is_public,
 *         kind: 'fork' | 'counterfactual',
 *         counterfactual: null | { trigger_round, label } }
 *     ],
 *     total_children: number,
 *     counterfactual: null | { trigger_round, label }
 *   }
 *
 * @param {string} simulationId
 */
export const getSimulationLineage = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/lineage`)
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
 * Build the absolute URL of the live spectator-watch page for a
 * simulation. Loads as a minimal full-viewport broadcast view —
 * a vanilla-JS poller updates the belief bar and round counter every
 * 15 s by hitting the existing `/api/simulation/<id>/embed-summary`
 * and `/api/simulation/<id>/run-status` REST endpoints. Once the
 * runner reaches a terminal state the polling stops and "View full
 * simulation →" / "Fork this scenario →" CTAs are revealed.
 *
 * Auto-unfurls as a 1200×630 image card when pasted into Twitter/X,
 * Discord, Slack, LinkedIn, iMessage — same OG / Twitter-card meta
 * tags as `/share/<id>`. Distinct from the share landing page in
 * that the watch URL is intended as a *live* broadcast link
 * (operators tweet it mid-run), where `/share/<id>` redirects
 * straight into the SPA simulation view.
 *
 * @param {string} simulationId
 * @param {string} [origin]
 * @returns {string}
 */
export const getWatchUrl = (simulationId, origin) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}/watch/${simulationId}`
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
 * Filter knobs mirror the gallery API — `consensus`, `quality`,
 * `outcome`, `q`, `sort`, `limit` — so callers can build a feed URL
 * that subscribes a reader (Feedly, n8n, Zapier, …) to a structured
 * slice of the corpus: "bullish + excellent + trending" rather than
 * the full firehose. Default/empty filters are omitted from the query
 * string so the URL stays clean when no filters are active.
 *
 * @param {Object} [options]
 * @param {('atom'|'rss')} [options.format='atom']
 * @param {boolean} [options.verified=false]
 * @param {string} [options.origin]
 * @param {('bullish'|'neutral'|'bearish')} [options.consensus]
 * @param {('excellent'|'good'|'fair'|'poor')} [options.quality]
 * @param {('correct'|'incorrect'|'partial')} [options.outcome]
 * @param {string} [options.q]
 * @param {('date'|'rounds'|'agents'|'trending')} [options.sort]
 * @param {number} [options.limit]
 * @returns {string}
 */
export const getFeedUrl = ({
  format = 'atom',
  verified = false,
  origin,
  consensus,
  quality,
  outcome,
  q,
  sort,
  limit,
} = {}) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  const ext = format === 'rss' ? 'rss' : 'atom'

  const params = new URLSearchParams()
  if (verified) params.set('verified', '1')
  if (consensus) params.set('consensus', consensus)
  if (quality) params.set('quality', quality)
  if (outcome) params.set('outcome', outcome)
  if (q && q.trim()) params.set('q', q.trim())
  if (sort && sort !== 'date') params.set('sort', sort)
  if (limit && Number.isFinite(Number(limit)) && Number(limit) > 0) {
    params.set('limit', String(Math.min(50, Math.max(1, Math.trunc(Number(limit))))))
  }

  const query = params.toString()
  return query ? `${base}/api/feed.${ext}?${query}` : `${base}/api/feed.${ext}`
}

/**
 * Build the absolute URL of the auto-generated public sitemap.
 *
 * The sitemap lists every published simulation's `/share/<id>` and
 * `/watch/<id>` URLs in the sitemaps.org 0.9 XML format, ready to
 * submit once to Google Search Console (or any compliant crawler).
 * `/robots.txt` advertises this URL via the standard `Sitemap:`
 * directive, so well-behaved bots discover it automatically.
 *
 * Returns the URL even when the operator has set ENABLE_SITEMAP=false
 * — the caller should consult `getSitemapConfig()` to know whether
 * the URL actually serves content (404 when disabled).
 *
 * @param {string} [origin]
 * @returns {string}
 */
export const getSitemapUrl = (origin) => {
  const base = origin || (typeof window !== 'undefined' ? window.location.origin : '')
  return `${base}/sitemap.xml`
}

/**
 * Fetch the public sitemap config — exposes whether `/sitemap.xml`
 * is enabled on this deployment so the EmbedDialog can render the
 * right hint without leaking any secret config.
 *
 * Response shape (under `data`):
 *   {
 *     enabled: boolean,
 *     sitemap_url: string | null
 *   }
 */
export const getSitemapConfig = () => {
  return service.get('/api/config/sitemap')
}

/**
 * Fetch the notification-channel config — tells the SPA which of the
 * three terminal-state notification channels (generic webhook, Discord
 * rich embed, Slack Block Kit) are wired up on this deployment, plus
 * whether the OriginTrail DKG citation surface is reachable. Only
 * presence booleans cross the wire; the underlying URLs (which often
 * carry an opaque secret in the path) stay server-side.
 *
 * Response shape (under `data`):
 *   {
 *     webhook_configured: boolean,
 *     discord_configured: boolean,
 *     slack_configured:   boolean,
 *     dkg_configured:     boolean,
 *     dkg_network:        "testnet" | "mainnet" | null,
 *   }
 *
 * @returns {Promise}
 */
export const getNotificationsConfig = () => {
  return service.get('/api/config/notifications')
}

/**
 * Read the persisted OriginTrail DKG citation for a published sim.
 * Returns 404 when the sim has never been anchored — same publish gate
 * as the reproduce.json endpoint. No daemon call.
 *
 * Response shape (under `data`):
 *   {
 *     ual: "urn:dkg:context-graph:…",
 *     merkle_root: "0x…",
 *     transaction_hash: "0x…",
 *     block_number: number | null,
 *     finalized: boolean,
 *     network: "testnet" | "mainnet",
 *     context_graph_id: string,
 *     assertion_name: string,
 *     reproduce_config_sha256: "sha256:…",
 *     explorer_url: string,
 *     published_at: ISO8601 string,
 *   }
 *
 * @param {string} simulationId
 */
export const getDkgCitation = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/dkg-citation`)
}

/**
 * Anchor a finished simulation's citation surface on the OriginTrail
 * DKG. Requires admin auth (the publish action has on-chain cost
 * implications: TRAC + gas). Idempotent — the second call returns the
 * cached citation without re-anchoring.
 *
 * Same response shape as ``getDkgCitation`` for the success case, with
 * an additional ``cached: boolean`` field at the top level signalling
 * whether the daemon was contacted.
 *
 * @param {string} simulationId
 * @param {{ force?: boolean }} [opts]
 */
export const publishToDkg = (simulationId, opts = {}) => {
  const body = opts.force ? { force: true } : {}
  return service.post(`/api/simulation/${simulationId}/publish-dkg`, body)
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
 * @param {Object} options - {
 *   limit?: number, offset?: number, page?: number,
 *   verifiedOnly?: boolean,
 *   q?: string,
 *   consensus?: 'bullish'|'neutral'|'bearish',
 *   quality?: 'excellent'|'good'|'fair'|'poor',
 *   outcome?: 'correct'|'incorrect'|'partial',
 *   sort?: 'date'|'rounds'|'agents'|'trending',
 * }
 *
 * `sort=trending` ranks public simulations by their cumulative
 * share-surface serve count (the sum of every per-surface counter the
 * `/api/simulation/<id>/surface-stats` endpoint exposes), so the most
 * widely-distributed runs float to the top of the gallery. Ties break
 * on date so the most-served-and-most-recent beats the
 * most-served-and-stale. Sims with no surface-stats file yet count as
 * zero serves and sort to the bottom.
 */
export const getPublicSimulations = (options = {}) => {
  const params = {}
  if (Number.isFinite(options.limit)) params.limit = options.limit
  if (Number.isFinite(options.offset)) params.offset = options.offset
  if (Number.isFinite(options.page)) params.page = options.page
  if (options.verifiedOnly) params.verified = '1'
  // Filter knobs added in the gallery search/filter PR. The backend
  // normalises (case + allowed values) so the frontend forwards
  // whatever the user typed without re-validating — single source of
  // truth on the API side.
  if (options.q) params.q = options.q
  if (options.consensus) params.consensus = options.consensus
  if (options.quality) params.quality = options.quality
  if (options.outcome) params.outcome = options.outcome
  if (options.sort) params.sort = options.sort
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
 * Fetch the recent webhook delivery attempts for a simulation.
 *
 * Reads `<sim_dir>/webhook-log.jsonl` server-side and returns the
 * newest 10 entries plus the all-time `total_attempts` count. Useful
 * for the EmbedDialog "Delivery history" panel — operators can verify
 * that the outbound webhook fired, what the downstream endpoint
 * returned, and how long the round trip took.
 *
 * Admin-token gated server-side. The SPA does not attach the token —
 * deployments behind a reverse proxy that adds the bearer header
 * automatically work; localhost dev installs without a configured
 * token will see a 503 and the panel renders a "configure first" hint.
 *
 * @param {string} simulationId
 */
export const getWebhookLog = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/webhook-log`)
}

/**
 * Re-fire the completion webhook for an already-finished simulation.
 *
 * Intended for the "Retry delivery" button in the EmbedDialog
 * Delivery history panel. The retry payload carries an extra
 * `retry: true` so downstream consumers can dedupe or surface replays.
 *
 * @param {string} simulationId
 * @param {Object} [data] - { status?: 'completed' | 'failed' }
 */
export const retryWebhookDelivery = (simulationId, data = {}) => {
  return service.post(`/api/simulation/${simulationId}/webhook-retry`, data)
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

