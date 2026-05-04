// Shareable scenario links — URL params that pre-fill the New Sim form on
// the home page. Mirrors the "Fork this scenario" affordance on the live
// watch / share-card surfaces (PR #67), but for un-run scenarios: any
// tweet, blog post, or Discord message can include a `?scenario=...&url=...`
// link that drops the reader directly into a pre-configured sim instead of
// the blank-page New Sim form.
//
// All inputs are treated as untrusted. The scenario / ask text fields land
// in <textarea> bindings (escaped on render) but we still strip HTML
// + javascript: URIs as defense-in-depth so a future v-html consumer can't
// be exploited by replaying a saved URL. Length caps prevent a malicious
// link from filling localStorage / form state with megabytes of text.

import DOMPurify from 'dompurify'

export const PREFILL_LIMITS = Object.freeze({
  MAX_SCENARIO_CHARS: 500,
  MAX_ASK_CHARS: 300,
  MAX_TEMPLATE_SLUG_CHARS: 80,
  MAX_URL_CHARS: 2000,
})

const SLUG_RE = /^[a-z0-9_-]+$/i

// Strip every C0 control character except \n, \r, \t (those are legitimate
// in the multi-line scenario textarea) plus DEL. Anything else is noise
// from a copy-paste or an attacker probing the field.
const CONTROL_CHARS_RE = new RegExp(
  '[\\u0000-\\u0008\\u000B\\u000C\\u000E-\\u001F\\u007F]',
  'g',
)

const stripText = (raw, max) => {
  if (typeof raw !== 'string') return ''
  // ALLOWED_TAGS:[] + ALLOWED_ATTR:[] returns plain text — every tag and
  // attribute is removed, including <script>, on*, javascript: URIs.
  const clean = DOMPurify.sanitize(raw, { ALLOWED_TAGS: [], ALLOWED_ATTR: [] })
  return clean.replace(CONTROL_CHARS_RE, '').slice(0, max).trim()
}

export const sanitizeScenarioText = (raw) =>
  stripText(raw, PREFILL_LIMITS.MAX_SCENARIO_CHARS)

export const sanitizeAskText = (raw) =>
  stripText(raw, PREFILL_LIMITS.MAX_ASK_CHARS)

export const sanitizeTemplateSlug = (raw) => {
  if (typeof raw !== 'string') return ''
  const trimmed = raw.trim().slice(0, PREFILL_LIMITS.MAX_TEMPLATE_SLUG_CHARS)
  return trimmed && SLUG_RE.test(trimmed) ? trimmed : ''
}

export const isValidHttpUrl = (raw) => {
  if (typeof raw !== 'string') return false
  const trimmed = raw.trim()
  if (!trimmed || trimmed.length > PREFILL_LIMITS.MAX_URL_CHARS) return false
  let parsed
  try {
    parsed = new URL(trimmed)
  } catch {
    return false
  }
  return parsed.protocol === 'http:' || parsed.protocol === 'https:'
}

const firstString = (v) => {
  if (typeof v === 'string') return v
  if (Array.isArray(v) && v.length > 0 && typeof v[0] === 'string') return v[0]
  return ''
}

export const readPrefilledParams = (query) => {
  if (!query || typeof query !== 'object') return {}
  const out = {}
  const scenario = sanitizeScenarioText(firstString(query.scenario))
  if (scenario) out.scenario = scenario
  const url = firstString(query.url).trim()
  if (isValidHttpUrl(url)) out.url = url
  const ask = sanitizeAskText(firstString(query.ask))
  if (ask) out.ask = ask
  const template = sanitizeTemplateSlug(firstString(query.template))
  if (template) out.template = template
  return out
}

export const hasAnyPrefill = (params) =>
  Boolean(params && (params.scenario || params.url || params.ask || params.template))

const resolveOrigin = (origin) => {
  const candidate =
    typeof origin === 'string' && origin
      ? origin
      : typeof window !== 'undefined' && window.location && window.location.origin
        ? window.location.origin
        : ''
  return candidate.replace(/\/+$/, '')
}

export const buildScenarioShareUrl = ({ origin, scenario, url, ask } = {}) => {
  const base = resolveOrigin(origin)
  const qs = new URLSearchParams()
  const cleanScenario = sanitizeScenarioText(scenario)
  if (cleanScenario) qs.set('scenario', cleanScenario)
  const trimmedUrl = typeof url === 'string' ? url.trim() : ''
  if (isValidHttpUrl(trimmedUrl)) qs.set('url', trimmedUrl)
  const cleanAsk = sanitizeAskText(ask)
  if (cleanAsk) qs.set('ask', cleanAsk)
  const q = qs.toString()
  return q ? `${base}/?${q}` : `${base}/`
}

export const buildTemplateShareUrl = (slug, origin) => {
  const base = resolveOrigin(origin)
  const safe = sanitizeTemplateSlug(slug)
  return safe ? `${base}/?template=${encodeURIComponent(safe)}` : `${base}/`
}
