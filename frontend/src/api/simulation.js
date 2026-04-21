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

