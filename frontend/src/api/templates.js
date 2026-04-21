import service from './index'

/**
 * List all available simulation templates (summaries only)
 */
export const listTemplates = () => {
  return service.get('/api/templates/list')
}

/**
 * Which backend feature flags are currently on (oracle seeds, per-agent MCP).
 * The frontend uses this to decide whether to render / enable toggles.
 */
export const getTemplateCapabilities = () => {
  return service.get('/api/templates/capabilities')
}

/**
 * Get a single template by ID (includes full seed_document).
 *
 * Pass ``enrich=true`` to opt into live oracle enrichment — the backend
 * dispatches the template's declared ``oracle_tools`` against FeedOracle
 * MCP and appends the results to the seed document before returning.
 * Requires ``ORACLE_SEED_ENABLED=true`` server-side; silently falls back
 * to the static seed when disabled or any call fails.
 *
 * @param {string} templateId
 * @param {{ enrich?: boolean }} opts
 */
export const getTemplate = (templateId, opts = {}) => {
  const params = opts.enrich ? { enrich: 'true' } : undefined
  return service.get(`/api/templates/${templateId}`, { params })
}
