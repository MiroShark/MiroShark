<template>
  <transition name="ss-fade">
    <div v-if="shouldShow" class="ss-wrap">
      <div class="ss-head">
        <span class="ss-label">
          <span class="ss-dot">◈</span> Smart Setup
          <span class="ss-sub">{{ statusLine }}</span>
        </span>
        <button
          v-if="!loading"
          class="ss-close"
          type="button"
          title="Dismiss suggestions"
          @click="dismiss"
        >×</button>
      </div>

      <div v-if="loading" class="ss-loading">
        <span class="ss-spinner"></span>
        Drafting three scenarios from your document…
      </div>

      <div v-else-if="suggestions.length > 0" class="ss-cards">
        <div
          v-for="(s, idx) in suggestions"
          :key="idx"
          class="ss-card"
          :class="cardClass(s.label)"
        >
          <div class="ss-card-head">
            <span class="ss-badge" :class="badgeClass(s.label)">{{ s.label }}</span>
            <span class="ss-range">Initial YES {{ s.expected_yes_range[0] }}–{{ s.expected_yes_range[1] }}%</span>
          </div>
          <div class="ss-question">{{ s.question }}</div>
          <div v-if="s.rationale" class="ss-rationale">{{ s.rationale }}</div>
          <button
            class="ss-use"
            type="button"
            @click="useSuggestion(s, idx)"
          >Use this →</button>
        </div>
      </div>

      <div v-else-if="error" class="ss-error">
        {{ error }}
      </div>
    </div>
  </transition>
</template>

<script setup>
/**
 * ScenarioSuggestions
 *
 * Eliminates the blank-page problem at simulation setup. Given a preview of
 * the user's uploaded document(s) or fetched URL(s), this component calls
 * `/api/simulation/suggest-scenarios`, debounces, and renders up to three
 * prediction-market-style scenario cards. Clicking "Use this →" emits a
 * `use` event with the chosen question so the parent can fill its textarea.
 *
 * Designed to be completely non-blocking: if the LLM is unavailable, the
 * backend times out, or the response is malformed, the panel simply does
 * not appear — the form below continues to work exactly as before.
 */

import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { suggestScenarios } from '../api/simulation'

const props = defineProps({
  textPreview: { type: String, default: '' },
  minChars: { type: Number, default: 120 },
  debounceMs: { type: Number, default: 800 }
})

const emit = defineEmits(['use', 'dismiss'])

const loading = ref(false)
const suggestions = ref([])
const error = ref('')
const dismissed = ref(false)
const lastPreview = ref('')
const debounceTimer = ref(null)
// Monotonic request counter so a late response from an outdated preview
// can't overwrite suggestions for the current preview.
const requestSeq = ref(0)

const shouldShow = computed(() => {
  if (dismissed.value) return false
  if (loading.value) return true
  if (error.value) return true
  return suggestions.value.length > 0
})

const statusLine = computed(() => {
  if (loading.value) return '// generating…'
  if (suggestions.value.length > 0) return '// pick one or refine your own'
  return ''
})

const cardClass = (label) => ({
  'ss-card-bull': label === 'Bull',
  'ss-card-bear': label === 'Bear',
  'ss-card-neutral': label === 'Neutral'
})

const badgeClass = (label) => ({
  'ss-badge-bull': label === 'Bull',
  'ss-badge-bear': label === 'Bear',
  'ss-badge-neutral': label === 'Neutral'
})

const useSuggestion = (s, idx) => {
  emit('use', { question: s.question, label: s.label, index: idx })
}

const dismiss = () => {
  dismissed.value = true
  suggestions.value = []
  error.value = ''
  emit('dismiss')
}

const fetchSuggestions = async (preview) => {
  const mySeq = ++requestSeq.value
  loading.value = true
  error.value = ''
  try {
    const res = await suggestScenarios({ text_preview: preview })
    if (mySeq !== requestSeq.value) return  // superseded
    if (!res || res.success === false) {
      suggestions.value = []
      return
    }
    const data = res.data || {}
    suggestions.value = Array.isArray(data.suggestions) ? data.suggestions : []
  } catch (_) {
    if (mySeq !== requestSeq.value) return
    // Treat failures as "no suggestions" — the underlying form still works.
    suggestions.value = []
  } finally {
    if (mySeq === requestSeq.value) {
      loading.value = false
    }
  }
}

const schedule = (preview) => {
  if (debounceTimer.value) {
    clearTimeout(debounceTimer.value)
    debounceTimer.value = null
  }
  debounceTimer.value = setTimeout(() => {
    fetchSuggestions(preview)
  }, props.debounceMs)
}

watch(
  () => props.textPreview,
  (next) => {
    const trimmed = (next || '').trim()
    if (trimmed.length < props.minChars) {
      suggestions.value = []
      loading.value = false
      error.value = ''
      lastPreview.value = ''
      if (debounceTimer.value) {
        clearTimeout(debounceTimer.value)
        debounceTimer.value = null
      }
      return
    }
    if (trimmed === lastPreview.value) return
    lastPreview.value = trimmed
    // Only un-dismiss if the preview actually changed (new document).
    dismissed.value = false
    schedule(trimmed)
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  if (debounceTimer.value) clearTimeout(debounceTimer.value)
})
</script>

<style scoped>
.ss-wrap {
  margin-top: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  background: rgba(255, 107, 26, 0.05);
  border: 2px dashed rgba(255, 107, 26, 0.35);
  border-radius: 4px;
  font-family: var(--font-mono);
  position: relative;
}

.ss-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-sm);
}

.ss-label {
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--color-orange);
  display: flex;
  align-items: center;
  gap: 8px;
}

.ss-dot {
  color: var(--color-orange);
  font-size: 12px;
}

.ss-sub {
  color: rgba(10, 10, 10, 0.45);
  font-size: 10px;
  letter-spacing: 1px;
  font-weight: normal;
}

.ss-close {
  background: none;
  border: none;
  color: rgba(10, 10, 10, 0.4);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  padding: 0 4px;
  transition: var(--transition-fast);
}

.ss-close:hover { color: var(--color-orange); }

.ss-loading {
  font-size: 11px;
  color: rgba(10, 10, 10, 0.55);
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 2px;
}

.ss-spinner {
  width: 10px;
  height: 10px;
  border: 2px solid rgba(255, 107, 26, 0.25);
  border-top-color: var(--color-orange);
  border-radius: 50%;
  display: inline-block;
  animation: ss-spin 0.8s linear infinite;
}

@keyframes ss-spin {
  to { transform: rotate(360deg); }
}

.ss-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}

.ss-card {
  background: var(--color-white);
  border: 2px solid rgba(10, 10, 10, 0.08);
  border-radius: 4px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: var(--transition-fast);
}

.ss-card:hover { border-color: var(--color-orange); }
.ss-card-bull { border-left: 4px solid var(--color-green); }
.ss-card-bear { border-left: 4px solid var(--color-red); }
.ss-card-neutral { border-left: 4px solid var(--color-amber); }

.ss-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.ss-badge {
  font-size: 9px;
  letter-spacing: 2px;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 2px;
  font-weight: 600;
  color: var(--color-white);
}

.ss-badge-bull { background: var(--color-green); }
.ss-badge-bear { background: var(--color-red); }
.ss-badge-neutral {
  background: var(--color-amber);
  color: var(--color-black);
}

.ss-range {
  font-size: 10px;
  color: rgba(10, 10, 10, 0.55);
  letter-spacing: 0.5px;
}

.ss-question {
  font-family: var(--font-display);
  font-size: 14px;
  color: var(--color-black);
  line-height: 1.35;
}

.ss-rationale {
  font-size: 10px;
  color: rgba(10, 10, 10, 0.55);
  line-height: 1.4;
  letter-spacing: 0.2px;
}

.ss-use {
  align-self: flex-start;
  margin-top: 4px;
  background: transparent;
  border: 1px solid var(--color-orange);
  color: var(--color-orange);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 2px;
  cursor: pointer;
  transition: var(--transition-fast);
}

.ss-use:hover {
  background: var(--color-orange);
  color: var(--color-white);
}

.ss-error {
  font-size: 11px;
  color: var(--color-red);
  letter-spacing: 0.5px;
}

/* Panel enter/leave */
.ss-fade-enter-active,
.ss-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.ss-fade-enter-from,
.ss-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
