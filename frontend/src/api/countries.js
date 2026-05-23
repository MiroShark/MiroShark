import service from './index'

/**
 * List available country packs for demographic grounding.
 *
 * @returns {Promise<{ success: boolean, data: { active_country: string|null, countries: Array<{
 *   code: string, name: string, flag_emoji: string, available: boolean,
 *   geography_field: string, geography_label: string, geography_count: number,
 *   max_agents: number, default_agents: number,
 * }> } }>}
 */
export function listCountries() {
  return service({ url: '/api/countries', method: 'get' })
}

/**
 * Fetch full filter schema for one country (geography values + groups,
 * filter field hints, agent caps).
 *
 * @param {string} code
 */
export function getCountry(code) {
  return service({ url: `/api/countries/${encodeURIComponent(code)}`, method: 'get' })
}

/**
 * Inspect the parquet schema for one country and return live min/max +
 * distinct-value option lists for each declared filter field. Triggers
 * a one-time HF snapshot download on the backend if not already cached,
 * so this call can be slow (seconds) on first use per country.
 *
 * @param {string} code
 * @param {{ max_distinct?: number }} [opts]
 */
export function getCountryFilterSchema(code, opts = {}) {
  return service({
    url: `/api/countries/${encodeURIComponent(code)}/filter-schema`,
    method: 'get',
    params: opts,
  })
}
