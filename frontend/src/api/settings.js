import service from './index'

/**
 * Get current active settings (API keys masked).
 * Returns every slot the modal displays: llm, smart, ner, wonderwall,
 * embedding, web_search_model, neo4j, available_presets.
 */
export const getSettings = () => {
  return service.get('/api/settings')
}

/**
 * Update settings at runtime. Every field is optional.
 *
 * @param {Object} data
 *   - preset:             "cheap" | "local"             (apply full preset)
 *   - preset_api_key:     string                        (filled into every preset key slot)
 *   - llm:                { provider, base_url, model_name, api_key }
 *   - smart:              { provider, base_url, model_name, api_key }
 *   - ner:                { base_url, model_name, api_key }
 *   - wonderwall:         { base_url, model_name, api_key }
 *   - embedding:          { provider, base_url, model_name, api_key, dimensions }
 *   - web_search_model:   string
 *   - neo4j:              { uri, user, password }
 */
export const updateSettings = (data) => {
  return service.post('/api/settings', data)
}

/**
 * Test the current LLM connection.
 * @returns {Promise<{ success, model, latency_ms, error }>}
 */
export const testLlmConnection = () => {
  return service.post('/api/settings/test-llm')
}

/**
 * Fire a sample event at a webhook URL — used by the Settings
 * "Send test event" button. Pass a URL to test an unsaved value;
 * omit it to test the currently saved Config.WEBHOOK_URL.
 *
 * @param {string} [url]
 * @param {string} [publicBaseUrl]
 * @returns {Promise<{ success, message, latency_ms, url_masked }>}
 */
export const testWebhook = (url, publicBaseUrl) => {
  const body = {}
  if (url) body.url = url
  if (publicBaseUrl) body.public_base_url = publicBaseUrl
  return service.post('/api/settings/test-webhook', body)
}
