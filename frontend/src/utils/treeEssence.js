/**
 * Pure helpers for the tree map view.
 *
 * extractEssence(summary): the first sentence of the summary, capped at
 * ~120 chars. No LLM, no async. Used as a 1-line headline on the map view.
 */

export function extractEssence(summary, maxLen = 120) {
  if (!summary || typeof summary !== 'string') return ''
  // Strip markdown markers that we don't want in a headline
  const clean = summary
    .replace(/^[#\s]+/m, '')
    .replace(/\*\*/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .trim()

  // Find the first sentence boundary
  const match = clean.match(/^(.*?[.!?])(\s|$)/s)
  let first = match ? match[1] : clean

  if (first.length > maxLen) {
    first = first.slice(0, maxLen).replace(/\s+\S*$/, '') + '…'
  }
  return first
}

export function truncate(text, maxLen = 80) {
  if (!text) return ''
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen).replace(/\s+\S*$/, '') + '…'
}

export function fetchedEvidenceCount(node) {
  if (!node?.evidence) return 0
  return node.evidence.filter(e => !e.fetch_error).length
}
