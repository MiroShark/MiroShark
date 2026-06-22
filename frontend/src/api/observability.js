import service from './index'

/**
 * Create an SSE EventSource for live event streaming
 * @param {string} simulationId - Optional simulation filter
 * @param {string} eventTypes - Comma-separated event type filter
 * @returns {EventSource}
 */
export const streamEvents = (simulationId, eventTypes) => {
  const params = new URLSearchParams()
  if (simulationId) params.set('simulation_id', simulationId)
  if (eventTypes) params.set('event_types', eventTypes)

  const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
  const streamPath = `/api/observability/events/stream?${params}`
  return new EventSource(apiBase ? `${apiBase}${streamPath}` : streamPath)
}

/**
 * Get aggregated observability stats
 * @param {string} simulationId
 */
export const getObservabilityStats = (simulationId) => {
  return service.get('/api/observability/stats', {
    params: simulationId ? { simulation_id: simulationId } : {}
  })
}
