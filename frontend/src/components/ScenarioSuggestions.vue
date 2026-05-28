<template>
  <transition name="ss-fade">
    <div v-if="shouldShow" class="ss-wrap">
      <div class="ss-head">
        <span class="ss-label">
          <span class="ss-dot">◈</span> {{ $tr('Smart Setup', '智能设置') }}
          <span class="ss-sub">{{ statusLine }}</span>
        </span>
        <button
          v-if="!loading"
          class="ss-close"
          type="button"
          :title="$tr('Dismiss suggestions', '关闭建议')"
          @click="dismiss"
        >×</button>
      </div>

      <div v-if="loading" class="ss-loading">
        <span class="ss-spinner"></span>
        {{ $tr('Drafting three scenarios from your document…', '正在根据你的文档起草三个情景…') }}
      </div>

      <div v-else-if="suggestions.length > 0" class="ss-cards">
        <div
          v-for="(s, idx) in suggestions"
          :key="idx"
          class="ss-card"
          :class="cardClass(s.label)"
        >
          <div class="ss-card-head">
            <span class="ss-badge" :class="badgeClass(s.label)">{{ s.label === 'Bull' ? $tr('Bull', '看涨') : s.label === 'Bear' ? $tr('Bear', '看跌') : s.label === 'Neutral' ? $tr('Neutral', '中立') : s.label }}</span>
            <span class="ss-range">{{ $tr('Initial YES', '初始 YES') }} {{ s.expected_yes_range[0] }}–{{ s.expected_yes_range[1] }}%</span>
          </div>
          <div class="ss-question">{{ s.question }}</div>
          <div v-if="s.rationale" class="ss-rationale">{{ s.rationale }}</div>
          <button
            class="ss-use"
            type="button"
            @click="useSuggestion(s, idx)"
          >{{ $tr('Use this →', '使用 →') }}</button>
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
import { tr } from '../i18n'

const props = defineProps({
  textPreview: { type: String, default: '' },
  simulationPrompt: { type: String, default: '' },
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
  if (loading.value) return tr('// generating…', '// 生成中…')
  if (suggestions.value.length > 0) return tr('// pick one or refine your own', '// 选择一个或自行完善')
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
    const res = await suggestScenarios({
      text_preview: preview,
      simulation_prompt: props.simulationPrompt || ''
    })
    // Only overwrite suggestions if this is still the latest call —
    // otherwise a stale slow response could wipe a fresh result.
    if (mySeq !== requestSeq.value) return
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
    // Always clear loading on response. A newer in-flight request (if any)
    // set loading=true again when it was scheduled, so this won't mask it.
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
  // Light loading state the moment a fetch is queued so the spinner reflects
  // the user's intent immediately, not 800ms later.
  loading.value = true
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
/* Smart Setup — reskinned to match the dark MiroShark Home.
   Bull / Bear / Neutral are remapped onto two distinguishable
   violets + a soft fuchsia so the semantic colour cues survive. */

.ss-wrap {
  margin-top: 0.65rem;
  padding: 0.95rem 1.1rem 1.05rem;
  border-radius: 1rem;
  background: linear-gradient(180deg, rgba(48, 36, 84, 0.45) 0%, rgba(20, 14, 42, 0.65) 100%);
  border: 1px solid rgba(167, 139, 250, 0.3);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.08),
    0 12px 28px -16px rgba(0, 0, 0, 0.7);
  font-family: 'Geist Mono', ui-monospace, 'SF Mono', Menlo, monospace;
  color: #f4f1ff;
  position: relative;
}

.ss-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.7rem;
  gap: 0.75rem;
}

.ss-label {
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: #c4b5fd;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.ss-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 9999px;
  background: radial-gradient(circle at 30% 30%, #ffffff 0%, #a78bfa 60%, #4c1d95 100%);
  box-shadow: 0 0 8px rgba(167, 139, 250, 0.9), 0 0 16px rgba(139, 92, 246, 0.6);
  font-size: 0;
  color: transparent;
}

.ss-sub {
  color: rgba(228, 222, 255, 0.55);
  font-size: 10px;
  letter-spacing: 0.04em;
  font-weight: normal;
}

.ss-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 9999px;
  background: linear-gradient(180deg, rgba(70, 55, 120, 0.5) 0%, rgba(20, 14, 42, 0.75) 100%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(228, 222, 255, 0.7);
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
  transition: color 180ms ease, border-color 180ms ease, transform 180ms ease;
}

.ss-close:hover {
  color: #ffffff;
  border-color: rgba(167, 139, 250, 0.55);
  transform: translateY(-1px);
}

.ss-loading {
  font-size: 11px;
  color: rgba(228, 222, 255, 0.6);
  letter-spacing: 0.04em;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 2px;
}

.ss-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(167, 139, 250, 0.22);
  border-top-color: #c4b5fd;
  border-radius: 50%;
  display: inline-block;
  animation: ss-spin 0.8s linear infinite;
  box-shadow: 0 0 12px rgba(167, 139, 250, 0.4);
}

@keyframes ss-spin {
  to { transform: rotate(360deg); }
}

.ss-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.6rem;
}

.ss-card {
  position: relative;
  background: linear-gradient(180deg, rgba(40, 30, 70, 0.65) 0%, rgba(18, 12, 38, 0.85) 100%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 0.85rem;
  padding: 0.7rem 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  color: #f4f1ff;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.1),
    inset 0 -1px 0 rgba(0, 0, 0, 0.45);
  transition: border-color 180ms ease, transform 180ms ease, box-shadow 180ms ease;
  overflow: hidden;
}

.ss-card:hover {
  border-color: rgba(167, 139, 250, 0.55);
  transform: translateY(-1px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.14),
    inset 0 -1px 0 rgba(0, 0, 0, 0.45),
    0 16px 36px -16px rgba(139, 92, 246, 0.5);
}

/* Left accent rails — semantic colour cue for direction. */
.ss-card::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: linear-gradient(180deg, #a78bfa, #c4b5fd);
  box-shadow: 0 0 12px rgba(167, 139, 250, 0.5);
}
.ss-card-bull::before { background: linear-gradient(180deg, #c4b5fd, #a78bfa); box-shadow: 0 0 14px rgba(196, 181, 253, 0.6); }
.ss-card-bear::before { background: linear-gradient(180deg, #f0abfc, #c084fc); box-shadow: 0 0 14px rgba(240, 171, 252, 0.55); }
.ss-card-neutral::before { background: linear-gradient(180deg, #fcd34d, #c4b5fd); box-shadow: 0 0 14px rgba(252, 211, 77, 0.4); }

.ss-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.ss-badge {
  font-size: 9px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  padding: 3px 9px;
  border-radius: 9999px;
  font-weight: 700;
  color: #ffffff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.25);
}
.ss-badge-bull    { background: linear-gradient(180deg, #a78bfa 0%, #6d4dd8 100%); }
.ss-badge-bear    { background: linear-gradient(180deg, #f0abfc 0%, #c084fc 100%); }
.ss-badge-neutral { background: linear-gradient(180deg, #fcd34d 0%, #d4a017 100%); color: #1a0f3a; }

.ss-range {
  font-size: 10px;
  color: rgba(228, 222, 255, 0.55);
  letter-spacing: 0.04em;
}

.ss-question {
  font-family: 'Geist', system-ui, -apple-system, sans-serif;
  font-size: 14px;
  color: #f4f1ff;
  line-height: 1.4;
  font-weight: 600;
}

.ss-rationale {
  font-size: 10.5px;
  color: rgba(228, 222, 255, 0.6);
  line-height: 1.5;
  letter-spacing: 0.01em;
}

.ss-use {
  align-self: flex-start;
  margin-top: 4px;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: linear-gradient(180deg, rgba(70, 55, 120, 0.55) 0%, rgba(20, 14, 42, 0.75) 100%);
  border: 1px solid rgba(167, 139, 250, 0.4);
  color: #ece8ff;
  font-family: inherit;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  padding: 6px 12px;
  border-radius: 9999px;
  cursor: pointer;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.2),
    inset 0 -1px 0 rgba(0, 0, 0, 0.35);
  transition: color 180ms ease, border-color 180ms ease, transform 180ms ease;
}

.ss-use:hover {
  color: #ffffff;
  border-color: rgba(196, 181, 253, 0.7);
  transform: translateY(-1px);
}

.ss-error {
  font-size: 11px;
  color: #f0abfc;
  letter-spacing: 0.04em;
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
