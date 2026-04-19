<template>
  <div class="what-if">
    <!-- Header -->
    <div class="wi-header">
      <div class="wi-title">
        <span class="wi-icon">◐</span>
        <span class="wi-label">WHAT IF? — COUNTERFACTUAL</span>
      </div>
      <button
        class="wi-export-btn"
        :disabled="!hasChartData"
        @click="downloadPNG"
        title="Download chart as PNG"
      >
        Export PNG ↓
      </button>
    </div>

    <div class="wi-hint">
      Pick up to {{ MAX_PICKS }} agents to remove, then recompute to see how
      consensus would have shifted. Uses existing trajectory data — no re-run.
    </div>

    <!-- Loading agents -->
    <div v-if="agentsLoading" class="wi-state">
      <div class="pulse-ring"></div>
      <span>Loading agents...</span>
    </div>

    <!-- No agents -->
    <div v-else-if="!agents.length" class="wi-state">
      <span>No influence data yet — run the simulation first.</span>
    </div>

    <template v-else>
      <!-- Agent picker row -->
      <div class="wi-picker">
        <div class="wi-picker-header">
          <span class="wi-picker-title">Top agents by influence</span>
          <button
            v-if="selectedNames.length"
            class="wi-clear"
            @click="clearSelection"
          >Clear ({{ selectedNames.length }})</button>
        </div>
        <div class="wi-agent-grid">
          <label
            v-for="a in agents"
            :key="a.agent_name"
            class="wi-agent-card"
            :class="{
              selected: selectedSet.has(a.agent_name),
              disabled: !selectedSet.has(a.agent_name) && selectedNames.length >= MAX_PICKS
            }"
          >
            <input
              type="checkbox"
              class="wi-check"
              :checked="selectedSet.has(a.agent_name)"
              :disabled="!selectedSet.has(a.agent_name) && selectedNames.length >= MAX_PICKS"
              @change="toggleAgent(a.agent_name)"
            />
            <span class="wi-rank">#{{ a.rank }}</span>
            <span class="wi-agent-name">{{ a.agent_name }}</span>
            <span class="wi-agent-score">{{ a.influence_score }}</span>
          </label>
        </div>
        <div class="wi-actions">
          <button
            class="wi-recompute"
            :disabled="!selectedNames.length || computing"
            @click="compute"
          >
            <span v-if="computing" class="wi-spinner"></span>
            {{ computing ? 'Recomputing...' : 'Recompute counterfactual' }}
          </button>
        </div>
      </div>

      <!-- Error -->
      <div v-if="error" class="wi-state wi-error">{{ error }}</div>

      <!-- Chart + summary -->
      <div v-if="hasChartData" class="wi-result">
        <div class="wi-chart-wrap">
          <svg
            :viewBox="`0 0 ${W} ${H}`"
            preserveAspectRatio="xMidYMid meet"
            class="wi-svg"
            ref="svgRef"
            xmlns="http://www.w3.org/2000/svg"
          >
            <!-- Grid -->
            <g v-for="pct in [0, 25, 50, 75, 100]" :key="'g' + pct">
              <line
                :x1="ML" :y1="yS(pct)"
                :x2="W - MR" :y2="yS(pct)"
                stroke="rgba(10,10,10,0.06)" stroke-width="1"
              />
              <text
                :x="ML - 5" :y="yS(pct) + 4"
                fill="rgba(10,10,10,0.35)" font-size="9"
                font-family="monospace" text-anchor="end"
              >{{ pct }}%</text>
            </g>

            <!-- 50% consensus line -->
            <line
              :x1="ML" :y1="yS(50)"
              :x2="W - MR" :y2="yS(50)"
              stroke="rgba(10,10,10,0.18)" stroke-width="1"
              stroke-dasharray="2,3"
            />

            <!-- Original bullish curve (muted, dashed) -->
            <path
              :d="originalPath"
              fill="none"
              stroke="rgba(20,184,166,0.55)"
              stroke-width="1.5"
              stroke-dasharray="5,3"
            />

            <!-- Counterfactual bullish curve (solid, highlighted) -->
            <path
              :d="counterfactualPath"
              fill="none"
              stroke="rgba(20,184,166,1)"
              stroke-width="2.2"
            />

            <!-- Endpoint dots -->
            <circle
              v-if="origEnd"
              :cx="origEnd.x" :cy="origEnd.y"
              r="3"
              fill="rgba(20,184,166,0.55)"
            />
            <circle
              v-if="cfEnd"
              :cx="cfEnd.x" :cy="cfEnd.y"
              r="4"
              fill="rgba(20,184,166,1)"
              stroke="#FAFAFA" stroke-width="1.5"
            />

            <!-- Consensus markers -->
            <g v-if="origData?.consensus_round != null">
              <line
                :x1="xS(origData.consensus_round)" :y1="MT"
                :x2="xS(origData.consensus_round)" :y2="H - MB"
                stroke="rgba(10,10,10,0.4)" stroke-width="1"
                stroke-dasharray="3,3"
              />
              <text
                :x="xS(origData.consensus_round) + 4" :y="MT + 10"
                fill="rgba(10,10,10,0.5)" font-size="9" font-family="monospace"
              >orig r{{ origData.consensus_round }}</text>
            </g>
            <g v-if="cfData?.consensus_round != null && cfData.consensus_round !== origData?.consensus_round">
              <line
                :x1="xS(cfData.consensus_round)" :y1="MT"
                :x2="xS(cfData.consensus_round)" :y2="H - MB"
                stroke="rgba(245,158,11,0.7)" stroke-width="1.2"
                stroke-dasharray="3,3"
              />
              <text
                :x="xS(cfData.consensus_round) + 4" :y="MT + 22"
                fill="rgba(245,158,11,0.85)" font-size="9" font-family="monospace"
              >cf r{{ cfData.consensus_round }}</text>
            </g>

            <!-- X axis -->
            <text
              v-for="r in xTicks"
              :key="'xt' + r"
              :x="xS(r)" :y="H - MB + 13"
              fill="rgba(10,10,10,0.35)" font-size="9"
              font-family="monospace" text-anchor="middle"
            >{{ r }}</text>
            <text
              :x="ML + (W - ML - MR) / 2" :y="H - 2"
              fill="rgba(10,10,10,0.3)" font-size="9"
              font-family="monospace" text-anchor="middle"
            >Round — bullish %</text>
          </svg>

          <div class="wi-legend">
            <span class="wi-legend-item">
              <span class="wi-legend-swatch orig"></span>
              Original ({{ origData?.agent_count ?? '–' }} agents)
            </span>
            <span class="wi-legend-item">
              <span class="wi-legend-swatch cf"></span>
              Counterfactual ({{ cfData?.agent_count ?? '–' }} agents)
            </span>
          </div>
        </div>

        <!-- Impact summary -->
        <div class="wi-impact">
          <div class="wi-impact-row">
            <span class="wi-impact-label">Final bullish share</span>
            <span class="wi-impact-values">
              <span class="wi-val orig">{{ fmtPct(origData?.final_bullish_pct) }}</span>
              <span class="wi-arrow">→</span>
              <span class="wi-val cf">{{ fmtPct(cfData?.final_bullish_pct) }}</span>
              <span
                v-if="result?.delta_final_bullish != null"
                class="wi-delta"
                :class="deltaClass(result.delta_final_bullish)"
              >{{ fmtDelta(result.delta_final_bullish) }} pts</span>
            </span>
          </div>
          <div class="wi-impact-row">
            <span class="wi-impact-label">Consensus round</span>
            <span class="wi-impact-values">
              <span class="wi-val orig">{{ fmtRound(origData?.consensus_round) }}</span>
              <span class="wi-arrow">→</span>
              <span class="wi-val cf">{{ fmtRound(cfData?.consensus_round) }}</span>
              <span
                v-if="result?.delta_consensus_round != null"
                class="wi-delta"
                :class="deltaClass(result.delta_consensus_round, true)"
              >{{ fmtDelta(result.delta_consensus_round) }} rounds</span>
            </span>
          </div>
          <div v-if="result?.impact" class="wi-impact-badge-row">
            <span
              class="wi-impact-badge"
              :class="'impact-' + result.impact"
            >{{ impactLabel(result.impact) }} influence</span>
          </div>
          <div v-if="result?.summary" class="wi-summary">
            {{ result.summary }}
          </div>
          <div v-if="result?.excluded_unresolved?.length" class="wi-warn">
            Couldn't match: {{ result.excluded_unresolved.join(', ') }}
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getInfluenceLeaderboard, getCounterfactualDrift } from '../api/simulation'

const props = defineProps({
  simulationId: { type: String, required: true },
  visible: { type: Boolean, default: false }
})

const MAX_PICKS = 3
const TOP_AGENTS = 12

const agents = ref([])
const agentsLoading = ref(false)
const selectedNames = ref([])
const selectedSet = computed(() => new Set(selectedNames.value))

const result = ref(null)
const computing = ref(false)
const error = ref('')
const svgRef = ref(null)

// SVG dimensions
const W = 560
const H = 220
const MT = 14
const MB = 26
const ML = 34
const MR = 12

const origData = computed(() => result.value?.original || null)
const cfData = computed(() => result.value?.counterfactual || null)

const hasChartData = computed(() =>
  !!(origData.value?.rounds?.length && cfData.value?.rounds?.length)
)

const allRounds = computed(() => {
  const s = new Set()
  ;(origData.value?.rounds || []).forEach((r) => s.add(r))
  ;(cfData.value?.rounds || []).forEach((r) => s.add(r))
  return Array.from(s).sort((a, b) => a - b)
})

const minR = computed(() => allRounds.value.length ? allRounds.value[0] : 1)
const maxR = computed(() => allRounds.value.length ? allRounds.value[allRounds.value.length - 1] : 10)

const xS = (r) => {
  const span = Math.max(maxR.value - minR.value, 1)
  return ML + ((r - minR.value) / span) * (W - ML - MR)
}

const yS = (pct) => {
  return MT + (1 - pct / 100) * (H - MT - MB)
}

const xTicks = computed(() => {
  const rs = allRounds.value
  if (!rs.length) return []
  if (rs.length <= 10) return rs
  const step = Math.ceil(rs.length / 10)
  return rs.filter((_, i) => i % step === 0 || i === rs.length - 1)
})

const linePath = (rounds, values) => {
  if (!rounds || !rounds.length) return ''
  return rounds.map((r, i) =>
    `${i === 0 ? 'M' : 'L'}${xS(r).toFixed(1)},${yS(values[i]).toFixed(1)}`
  ).join(' ')
}

const originalPath = computed(() => {
  if (!origData.value) return ''
  return linePath(origData.value.rounds, origData.value.bullish)
})

const counterfactualPath = computed(() => {
  if (!cfData.value) return ''
  return linePath(cfData.value.rounds, cfData.value.bullish)
})

const origEnd = computed(() => {
  if (!origData.value?.rounds?.length) return null
  const rs = origData.value.rounds
  const vs = origData.value.bullish
  return { x: xS(rs[rs.length - 1]), y: yS(vs[vs.length - 1]) }
})

const cfEnd = computed(() => {
  if (!cfData.value?.rounds?.length) return null
  const rs = cfData.value.rounds
  const vs = cfData.value.bullish
  return { x: xS(rs[rs.length - 1]), y: yS(vs[vs.length - 1]) }
})

const fmtPct = (v) => (v == null ? '–' : `${v}%`)
const fmtRound = (v) => (v == null ? 'no consensus' : `r${v}`)
const fmtDelta = (v) => {
  if (v == null) return '–'
  const sign = v > 0 ? '+' : ''
  return `${sign}${v}`
}
const deltaClass = (v, invert = false) => {
  if (v == null) return 'neutral'
  const positive = invert ? v < 0 : v > 0
  const negative = invert ? v > 0 : v < 0
  if (positive) return 'positive'
  if (negative) return 'negative'
  return 'neutral'
}
const impactLabel = (kind) => {
  if (kind === 'strong') return 'Strong'
  if (kind === 'moderate') return 'Moderate'
  return 'Minimal'
}

const loadAgents = async () => {
  if (!props.simulationId) return
  agentsLoading.value = true
  try {
    const res = await getInfluenceLeaderboard(props.simulationId)
    if (res?.success && res.data?.agents) {
      agents.value = res.data.agents.slice(0, TOP_AGENTS)
    } else {
      agents.value = []
    }
  } catch {
    agents.value = []
  } finally {
    agentsLoading.value = false
  }
}

const toggleAgent = (name) => {
  const i = selectedNames.value.indexOf(name)
  if (i === -1) {
    if (selectedNames.value.length >= MAX_PICKS) return
    selectedNames.value = [...selectedNames.value, name]
  } else {
    selectedNames.value = selectedNames.value.filter((n) => n !== name)
  }
}

const clearSelection = () => {
  selectedNames.value = []
  result.value = null
}

const compute = async () => {
  if (!selectedNames.value.length) return
  computing.value = true
  error.value = ''
  try {
    const res = await getCounterfactualDrift(props.simulationId, selectedNames.value)
    if (res?.success && res.data) {
      result.value = res.data
    } else if (res?.success && !res.data) {
      error.value = res.message || 'No trajectory data available for this simulation.'
    } else {
      error.value = res?.error || 'Failed to compute counterfactual.'
    }
  } catch (err) {
    error.value = err?.message || 'Failed to compute counterfactual.'
  } finally {
    computing.value = false
  }
}

const downloadPNG = () => {
  const svg = svgRef.value
  if (!svg) return
  const serializer = new XMLSerializer()
  const svgStr = serializer.serializeToString(svg)
  const canvas = document.createElement('canvas')
  canvas.width = W * 2
  canvas.height = H * 2
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = '#FAFAFA'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  const img = new Image()
  img.onload = () => {
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    const a = document.createElement('a')
    a.download = `counterfactual-${props.simulationId}.png`
    a.href = canvas.toDataURL('image/png')
    a.click()
  }
  img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgStr)))
}

watch(() => props.visible, (val) => {
  if (val && !agents.value.length) loadAgents()
})
watch(() => props.simulationId, () => {
  if (props.visible) {
    agents.value = []
    selectedNames.value = []
    result.value = null
    loadAgents()
  }
})
onMounted(() => { if (props.visible) loadAgents() })
</script>

<style scoped>
.what-if {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow-y: auto;
  font-family: var(--font-mono);
  background: var(--background);
}

.wi-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.08);
  flex-shrink: 0;
}

.wi-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  letter-spacing: 0.1em;
  color: rgba(10,10,10,0.75);
}

.wi-icon { font-size: 14px; color: rgba(20,184,166,0.9); }

.wi-export-btn {
  background: transparent;
  border: 1px solid rgba(10,10,10,0.15);
  color: rgba(10,10,10,0.6);
  padding: 4px 10px;
  font-family: inherit;
  font-size: 10px;
  letter-spacing: 0.05em;
  cursor: pointer;
  border-radius: 2px;
}
.wi-export-btn:hover:not(:disabled) {
  background: rgba(10,10,10,0.04);
  color: rgba(10,10,10,0.85);
}
.wi-export-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.wi-hint {
  padding: 8px 16px;
  font-size: 11px;
  line-height: 1.4;
  color: rgba(10,10,10,0.55);
  border-bottom: 1px solid rgba(10,10,10,0.05);
}

.wi-state {
  padding: 24px 16px;
  text-align: center;
  color: rgba(10,10,10,0.55);
  font-size: 11px;
}
.wi-state.wi-error { color: rgba(239,68,68,0.9); }

.pulse-ring {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: rgba(20,184,166,0.8);
  margin-right: 8px;
  animation: wi-pulse 1.4s ease-in-out infinite;
}
@keyframes wi-pulse {
  0%, 100% { opacity: 0.4; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1.1); }
}

.wi-picker {
  padding: 12px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.05);
}

.wi-picker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.wi-picker-title {
  font-size: 10px;
  letter-spacing: 0.1em;
  color: rgba(10,10,10,0.5);
}
.wi-clear {
  background: transparent;
  border: none;
  font-family: inherit;
  font-size: 10px;
  color: rgba(10,10,10,0.55);
  cursor: pointer;
  padding: 2px 6px;
}
.wi-clear:hover { color: rgba(10,10,10,0.9); text-decoration: underline; }

.wi-agent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 6px;
}

.wi-agent-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border: 1px solid rgba(10,10,10,0.12);
  border-radius: 2px;
  cursor: pointer;
  font-size: 11px;
  color: rgba(10,10,10,0.8);
  transition: background-color 0.12s, border-color 0.12s;
}
.wi-agent-card:hover:not(.disabled) {
  background: rgba(20,184,166,0.06);
  border-color: rgba(20,184,166,0.4);
}
.wi-agent-card.selected {
  background: rgba(20,184,166,0.1);
  border-color: rgba(20,184,166,0.7);
}
.wi-agent-card.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.wi-check { margin: 0; cursor: inherit; }

.wi-rank {
  font-size: 10px;
  color: rgba(10,10,10,0.45);
  min-width: 24px;
}
.wi-agent-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wi-agent-score {
  font-size: 10px;
  color: rgba(10,10,10,0.5);
}

.wi-actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}

.wi-recompute {
  background: rgba(20,184,166,1);
  color: #fff;
  border: none;
  padding: 6px 14px;
  font-family: inherit;
  font-size: 11px;
  letter-spacing: 0.05em;
  cursor: pointer;
  border-radius: 2px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.wi-recompute:hover:not(:disabled) { background: rgba(17,164,148,1); }
.wi-recompute:disabled {
  background: rgba(10,10,10,0.15);
  cursor: not-allowed;
}

.wi-spinner {
  width: 10px;
  height: 10px;
  border: 2px solid rgba(255,255,255,0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: wi-spin 0.8s linear infinite;
}
@keyframes wi-spin { to { transform: rotate(360deg); } }

.wi-result {
  padding: 10px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.wi-chart-wrap {
  background: rgba(10,10,10,0.02);
  padding: 10px 6px 4px;
  border-radius: 2px;
}

.wi-svg { width: 100%; height: auto; display: block; }

.wi-legend {
  display: flex;
  gap: 16px;
  padding: 6px 8px 0;
  font-size: 10px;
  color: rgba(10,10,10,0.6);
}
.wi-legend-item { display: inline-flex; align-items: center; gap: 6px; }
.wi-legend-swatch {
  width: 18px;
  height: 2px;
  display: inline-block;
}
.wi-legend-swatch.orig {
  background: repeating-linear-gradient(
    90deg,
    rgba(20,184,166,0.55) 0,
    rgba(20,184,166,0.55) 4px,
    transparent 4px,
    transparent 7px
  );
}
.wi-legend-swatch.cf {
  background: rgba(20,184,166,1);
  height: 3px;
}

.wi-impact {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  border: 1px solid rgba(10,10,10,0.08);
  border-radius: 2px;
  background: rgba(10,10,10,0.02);
}

.wi-impact-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  gap: 12px;
}
.wi-impact-label {
  color: rgba(10,10,10,0.55);
  letter-spacing: 0.04em;
}
.wi-impact-values {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: monospace;
}
.wi-val.orig { color: rgba(10,10,10,0.55); }
.wi-val.cf { color: rgba(10,10,10,0.9); font-weight: 600; }
.wi-arrow { color: rgba(10,10,10,0.3); }

.wi-delta {
  padding: 1px 6px;
  border-radius: 2px;
  font-size: 10px;
  font-weight: 600;
  border: 1px solid transparent;
}
.wi-delta.positive { color: rgba(20,184,166,1); border-color: rgba(20,184,166,0.35); }
.wi-delta.negative { color: rgba(239,68,68,0.9); border-color: rgba(239,68,68,0.35); }
.wi-delta.neutral  { color: rgba(10,10,10,0.5); border-color: rgba(10,10,10,0.15); }

.wi-impact-badge-row { margin-top: 4px; }
.wi-impact-badge {
  display: inline-block;
  padding: 3px 8px;
  font-size: 10px;
  letter-spacing: 0.08em;
  border-radius: 2px;
  border: 1px solid transparent;
}
.wi-impact-badge.impact-strong {
  color: rgba(20,184,166,1);
  background: rgba(20,184,166,0.08);
  border-color: rgba(20,184,166,0.4);
}
.wi-impact-badge.impact-moderate {
  color: rgba(234,179,8,1);
  background: rgba(234,179,8,0.08);
  border-color: rgba(234,179,8,0.4);
}
.wi-impact-badge.impact-minimal {
  color: rgba(10,10,10,0.5);
  background: rgba(10,10,10,0.04);
  border-color: rgba(10,10,10,0.15);
}

.wi-summary {
  font-size: 11px;
  line-height: 1.5;
  color: rgba(10,10,10,0.75);
  padding-top: 4px;
  border-top: 1px solid rgba(10,10,10,0.06);
}

.wi-warn {
  font-size: 10px;
  color: rgba(234,88,12,0.85);
  padding-top: 2px;
}
</style>
