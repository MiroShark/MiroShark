import service, { requestWithRetry } from './index'

/**
 * Post a turn in the seed chat conversation
 * @param {Object} data - { messages, seed_state, session_id? }
 */
export const postTurn = (data) => {
  return requestWithRetry(() => service.post('/api/seed-chat/turn', data), 3, 1000)
}

/**
 * Launch a new seed chat session
 * @param {Object} data - { seed }
 */
export const postLaunch = (data) => {
  return requestWithRetry(() => service.post('/api/seed-chat/launch', data), 3, 1000)
}

/**
 * List recent seed-chat sessions (summaries only).
 * Returns { sessions: [{id, title, created_at, updated_at}, ...] }.
 */
export const listSessions = () => {
  return requestWithRetry(() => service.get('/api/seed-chat/sessions'), 3, 1000)
}

/**
 * Load a single session in full (id, title, messages, seed_state, ready_to_launch, ...)
 */
export const getSession = (id) => {
  return requestWithRetry(() => service.get(`/api/seed-chat/sessions/${id}`), 3, 1000)
}

/**
 * Create a new empty session and return it.
 */
export const createSession = () => {
  return requestWithRetry(() => service.post('/api/seed-chat/sessions'), 3, 1000)
}

/**
 * Run intent-guided research for an active session.
 * Long-running (30-90s); use a wider timeout and skip retry.
 */
export const postResearch = (data) => {
  return service.post('/api/seed-chat/research', data, { timeout: 240000 })
}

/**
 * Research a single claim within a session. Same long-running profile as /research.
 */
export const postResearchClaim = (data) => {
  return service.post('/api/seed-chat/research-claim', data, { timeout: 240000 })
}

/**
 * Generate balanced video ad scripts from session's seed + brief + sources.
 * Long-running like /launch — uses 240s timeout.
 */
export const postAdScripts = (data) => {
  return service.post('/api/seed-chat/ad-scripts', data, { timeout: 240000 })
}
