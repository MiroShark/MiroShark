<template>
  <div class="what-if">
    <!-- Header -->
    <div class="wi-header">
      <div class="wi-title">
        <span class="wi-icon">◐</span>
        <span class="wi-label">{{ $tr('WHAT IF? — COUNTERFACTUAL', '假设性 — 反事实') }}</span>
      </div>
      <div class="wi-header-actions">
        <button
          class="wi-export-btn"
          :disabled="!hasChartData || exporting || !copySupported"
          :title="copySupported ? $tr('Copy chart as PNG (with MiroShark watermark)', '复制图表为 PNG(含 MiroShark 水印)') : $tr('Image copy not supported in this browser', '此浏览器不支持图像复制')"
          @click="copyChart"
        >
          {{ copiedFlash ? $tr('Copied', '已复制') : $tr('Copy', '复制') }}
        </button>
        <button
          class="wi-export-btn"
          :disabled="!hasChartData || exporting"
          @click="downloadChart"
          :title="$tr('Download chart as PNG (with MiroShark watermark)', '下载图表为 PNG(含 MiroShark 水印)')"
        >
          {{ $tr('Download ↓', '下载 ↓') }}
        </button>
      </div>
    </div>

    <div class="wi-hint">
      {{ $tr('Pick up to', '最多挑选') }} {{ MAX_PICKS }} {{ $tr('agents to remove, then recompute to see how consensus would have shifted. Uses existing trajectory data — no re-run.', '个智能体进行移除,然后重新计算以查看共识将如何变化。使用现有轨迹数据 — 无需重新运行。') }}
    </div>

    <!-- Loading agents -->
    <div v-if="agentsLoading" class="wi-state">
      <div class="pulse-ring"></div>
      <span>{{ $tr('Loading agents...', '加载智能体中...') }}</span>
    </div>

    <!-- No agents -->
    <div v-else-if="!agents.length" class="wi-state">
      <span>{{ $tr('No influence data yet — run the simulation first.', '暂无影响力数据 — 请先运行模拟。') }}</span>
    </div>

    <template v-else>
      <!-- Agent picker row -->
      <div class="wi-picker">
        <div class="wi-picker-header">
          <span class="wi-picker-title">{{ $tr('Top agents by influence', '影响力排名靠前的智能体') }}</span>
          <button
            v-if="selectedNames.length"
            class="wi-clear"
            @click="clearSelection"
          >{{ $tr('Clear', '清除') }} ({{ selectedNames.length }})</button>
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
            {{ computing ? $tr('Recomputing...', '重新计算中...') : $tr('Recompute counterfactual', '重新计算反事实') }}
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
                font-family="'Space Mono', monospace" text-anchor="end"
              >{{ pct }}%</text>
            </g>

            <!-- 50% consensus line -->
            <line
              :x1="ML" :y1="yS(50)"
              :x2="W - MR" :y2="yS(50)"
              stroke="rgba(10,10,10,0.18)" stroke-width="1"
              stroke-dasharray="2,3"
            />

            <!-- Original bullish curve (muted gray, dashed) -->
            <path
              :d="originalPath"
              fill="none"
              stroke="rgba(10,10,10,0.35)"
              stroke-width="1.5"
              stroke-dasharray="5,3"
            />

            <!-- Counterfactual bullish curve (orange, solid highlight) -->
            <path
              :d="counterfactualPath"
              fill="none"
              stroke="#FF6B1A"
              stroke-width="2.2"
            />

            <!-- Endpoint dots -->
            <circle
              v-if="origEnd"
              :cx="origEnd.x" :cy="origEnd.y"
              r="3"
              fill="rgba(10,10,10,0.35)"
            />
            <circle
              v-if="cfEnd"
              :cx="cfEnd.x" :cy="cfEnd.y"
              r="4"
              fill="#FF6B1A"
              stroke="#FAFAFA" stroke-width="1.5"
            />

            <!-- Consensus markers — orig in gray, cf in green (design bicolor) -->
            <g v-if="origData?.consensus_round != null">
              <line
                :x1="xS(origData.consensus_round)" :y1="MT"
                :x2="xS(origData.consensus_round)" :y2="H - MB"
                stroke="rgba(10,10,10,0.3)" stroke-width="1"
                stroke-dasharray="3,3"
              />
              <text
                :x="xS(origData.consensus_round) + 4" :y="MT + 10"
                fill="rgba(10,10,10,0.45)" font-size="9"
                font-family="'Space Mono', monospace"
              >{{ $tr('orig r', '原 r') }}{{ origData.consensus_round }}</text>
            </g>
            <g v-if="cfData?.consensus_round != null && cfData.consensus_round !== origData?.consensus_round">
              <line
                :x1="xS(cfData.consensus_round)" :y1="MT"
                :x2="xS(cfData.consensus_round)" :y2="H - MB"
                stroke="#43C165" stroke-width="1.2"
                stroke-dasharray="3,3"
              />
              <text
                :x="xS(cfData.consensus_round) + 4" :y="MT + 22"
                fill="#43C165" font-size="9"
                font-family="'Space Mono', monospace"
              >{{ $tr('cf r', '反 r') }}{{ cfData.consensus_round }}</text>
            </g>

            <!-- X axis -->
            <text
              v-for="r in xTicks"
              :key="'xt' + r"
              :x="xS(r)" :y="H - MB + 13"
              fill="rgba(10,10,10,0.35)" font-size="9"
              font-family="'Space Mono', monospace" text-anchor="middle"
            >{{ r }}</text>
            <text
              :x="ML + (W - ML - MR) / 2" :y="H - 2"
              fill="rgba(10,10,10,0.3)" font-size="9"
              font-family="'Space Mono', monospace" text-anchor="middle"
            >{{ $tr('Round — bullish %', '轮次 — 看涨 %') }}</text>
          </svg>

          <div class="wi-legend">
            <span class="wi-legend-item">
              <span class="wi-legend-swatch orig"></span>
              {{ $tr('Original', '原始') }} ({{ origData?.agent_count ?? '–' }} {{ $tr('agents', '智能体') }})
            </span>
            <span class="wi-legend-item">
              <span class="wi-legend-swatch cf"></span>
              {{ $tr('Counterfactual', '反事实') }} ({{ cfData?.agent_count ?? '–' }} {{ $tr('agents', '智能体') }})
            </span>
          </div>
        </div>

        <!-- Impact summary -->
        <div class="wi-impact">
          <div class="wi-impact-row">
            <span class="wi-impact-label">{{ $tr('Final bullish share', '最终看涨占比') }}</span>
            <span class="wi-impact-values">
              <span class="wi-val orig">{{ fmtPct(origData?.final_bullish_pct) }}</span>
              <span class="wi-arrow">→</span>
              <span class="wi-val cf">{{ fmtPct(cfData?.final_bullish_pct) }}</span>
              <span
                v-if="result?.delta_final_bullish != null"
                class="wi-delta"
                :class="deltaClass(result.delta_final_bullish)"
              >{{ fmtDelta(result.delta_final_bullish) }} {{ $tr('pts', '点') }}</span>
            </span>
          </div>
          <div class="wi-impact-row">
            <span class="wi-impact-label">{{ $tr('Consensus round', '共识轮次') }}</span>
            <span class="wi-impact-values">
              <span class="wi-val orig">{{ fmtRound(origData?.consensus_round) }}</span>
              <span class="wi-arrow">→</span>
              <span class="wi-val cf">{{ fmtRound(cfData?.consensus_round) }}</span>
              <span
                v-if="result?.delta_consensus_round != null"
                class="wi-delta"
                :class="deltaClass(result.delta_consensus_round, true)"
              >{{ fmtDelta(result.delta_consensus_round) }} {{ $tr('rounds', '轮次') }}</span>
            </span>
          </div>
          <div v-if="result?.impact" class="wi-impact-badge-row">
            <span
              class="wi-impact-badge"
              :class="'impact-' + result.impact"
            >{{ impactLabel(result.impact) }} {{ $tr('influence', '影响力') }}</span>
          </div>
          <div v-if="result?.summary" class="wi-summary">
            {{ result.summary }}
          </div>
          <div v-if="result?.excluded_unresolved?.length" class="wi-warn">
            {{ $tr(`Couldn't match:`, '未能匹配:') }} {{ result.excluded_unresolved.join(', ') }}
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { getInfluenceLeaderboard, getCounterfactualDrift } from '../api/simulation'
import {
  renderSvgToCanvas,
  downloadCanvas,
  copyCanvasToClipboard,
  canCopyImageToClipboard,
  buildTitledHeader,
} from '../utils/chartExport'
import { tr } from '../i18n'

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
const exporting = ref(false)
const copiedFlash = ref(false)
let copiedFlashTimer = null
const copySupported = canCopyImageToClipboard()

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
const fmtRound = (v) => (v == null ? tr('no consensus', '未达成共识') : `r${v}`)
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
  if (kind === 'strong') return tr('Strong', '强')
  if (kind === 'moderate') return tr('Moderate', '中等')
  return tr('Minimal', '微小')
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
      error.value = res.message || tr('No trajectory data available for this simulation.', '此模拟暂无轨迹数据。')
    } else {
      error.value = res?.error || tr('Failed to compute counterfactual.', '反事实计算失败。')
    }
  } catch (err) {
    error.value = err?.message || tr('Failed to compute counterfactual.', '反事实计算失败。')
  } finally {
    computing.value = false
  }
}

// ── Chart export (copy + download as PNG, with MiroShark watermark) ──

const _buildExportCanvas = () => {
  if (!svgRef.value || !hasChartData.value) {
    throw new Error('No chart to export')
  }
  const removed = selectedNames.value.length
    ? `${tr('Removed', '已移除')} ${selectedNames.value.join(', ')}`
    : tr('Counterfactual drift', '反事实漂移')
  const deltaStr = result.value?.delta_final_bullish != null
    ? `${result.value.delta_final_bullish >= 0 ? '+' : ''}${result.value.delta_final_bullish} ${tr('pts on bullish share', '点看涨占比')}`
    : null
  const { drawHeader, headerHeight } = buildTitledHeader({
    title: `${tr('What If?', '假设性?')} — ${removed}`,
    subtitle: deltaStr,
    width: W,
  })
  return renderSvgToCanvas(svgRef.value, {
    width: W,
    height: H,
    scale: 2,
    headerHeight,
    drawHeader,
    subtitle: `${props.simulationId} · ${new Date().toLocaleDateString()}`,
  })
}

const _flashCopied = () => {
  copiedFlash.value = true
  if (copiedFlashTimer) clearTimeout(copiedFlashTimer)
  copiedFlashTimer = setTimeout(() => { copiedFlash.value = false }, 1600)
}

async function copyChart() {
  if (exporting.value || !hasChartData.value) return
  exporting.value = true
  try {
    const canvas = await _buildExportCanvas()
    await copyCanvasToClipboard(canvas)
    _flashCopied()
  } catch (err) {
    console.warn('[what-if] copy failed, falling back to download:', err)
    try {
      const canvas = await _buildExportCanvas()
      downloadCanvas(canvas, `miroshark-whatif-${props.simulationId}.png`)
    } catch (err2) {
      console.error('[what-if] download fallback failed:', err2)
    }
  } finally {
    exporting.value = false
  }
}

async function downloadChart() {
  if (exporting.value || !hasChartData.value) return
  exporting.value = true
  try {
    const canvas = await _buildExportCanvas()
    downloadCanvas(canvas, `miroshark-whatif-${props.simulationId}.png`)
  } catch (err) {
    console.error('[what-if] download failed:', err)
  } finally {
    exporting.value = false
  }
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
onBeforeUnmount(() => {
  if (copiedFlashTimer) clearTimeout(copiedFlashTimer)
})
</script>

<style scoped>
/* ── Container — mirrors .influence-leaderboard (Space Mono, light bg) ── */
.what-if {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow-y: auto;
  font-family: var(--font-mono);
  background: var(--background);
}

/* ── Header — mirrors .lb-header ── */
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
}

.wi-icon {
  font-size: 14px;
  color: var(--color-orange);
}

.wi-label {
  font-size: 12px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.5);
}

/* Header action cluster */
.wi-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── Export button — mirrors .export-btn ── */
.wi-export-btn {
  background: none;
  border: 1px solid rgba(10,10,10,0.15);
  color: rgba(10,10,10,0.5);
  padding: 4px 10px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 1px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.wi-export-btn:hover:not(:disabled) {
  border-color: var(--color-orange);
  color: var(--color-orange);
}
.wi-export-btn:disabled { opacity: 0.3; cursor: not-allowed; }

.wi-hint {
  padding: 8px 16px;
  font-size: 11px;
  line-height: 1.5;
  color: rgba(10,10,10,0.5);
  border-bottom: 1px solid rgba(10,10,10,0.05);
  letter-spacing: 0.3px;
}

/* ── States — mirrors .lb-loading / .lb-empty / .lb-error ── */
.wi-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px;
  text-align: center;
  color: rgba(10,10,10,0.35);
  font-size: 13px;
  letter-spacing: 1px;
}
.wi-state.wi-error { color: var(--color-red); }

.pulse-ring {
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-orange);
  border-radius: 50%;
  animation: wi-pulse 1.2s ease-in-out infinite;
}
@keyframes wi-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.4); opacity: 0.4; }
}

.wi-picker {
  padding: 12px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.05);
}

.wi-picker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.wi-picker-title {
  font-size: 10px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.4);
}
.wi-clear {
  background: none;
  border: none;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 1px;
  color: rgba(10,10,10,0.5);
  cursor: pointer;
  padding: 2px 6px;
  transition: color 0.15s;
}
.wi-clear:hover { color: var(--color-orange); }

.wi-agent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 6px;
}

/* ── Agent card — same hover/selected pattern as the leaderboard's top-three
   accent (orange left-border, no radius), keeps the row-like feel ── */
.wi-agent-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid rgba(10,10,10,0.12);
  cursor: pointer;
  font-size: 11px;
  color: rgba(10,10,10,0.7);
  transition: background-color 0.12s, border-color 0.12s;
}
.wi-agent-card:hover:not(.disabled) {
  background: rgba(10,10,10,0.02);
  border-color: rgba(255, 107, 26, 0.35);
}
.wi-agent-card.selected {
  background: rgba(255, 107, 26, 0.06);
  border-color: var(--color-orange);
  color: var(--foreground);
}
.wi-agent-card.disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.wi-check { margin: 0; cursor: inherit; accent-color: var(--color-orange); }

.wi-rank {
  font-size: 10px;
  color: rgba(10,10,10,0.4);
  min-width: 24px;
  font-weight: 700;
}
.wi-agent-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 700;
}
.wi-agent-score {
  font-size: 10px;
  color: var(--color-orange);
  font-weight: 700;
}

.wi-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

/* ── Recompute — primary CTA, matches .action-btn.primary (black filled) ── */
.wi-recompute {
  background: var(--color-black);
  color: var(--color-white);
  border: 2px solid var(--color-black);
  padding: 8px 16px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 2.5px;
  text-transform: uppercase;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: opacity 0.15s ease;
}
.wi-recompute:hover:not(:disabled) { opacity: 0.9; }
.wi-recompute:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.wi-spinner {
  width: 10px;
  height: 10px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: var(--color-orange);
  border-radius: 50%;
  animation: wi-spin 0.8s linear infinite;
}
@keyframes wi-spin { to { transform: rotate(360deg); } }

.wi-result {
  padding: 12px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.wi-chart-wrap {
  background: rgba(10,10,10,0.02);
  border: 1px solid rgba(10,10,10,0.06);
  padding: 10px 6px 4px;
}

.wi-svg { width: 100%; height: auto; display: block; }

.wi-legend {
  display: flex;
  gap: 16px;
  padding: 6px 8px 0;
  font-size: 10px;
  letter-spacing: 1px;
  color: rgba(10,10,10,0.5);
}
.wi-legend-item { display: inline-flex; align-items: center; gap: 6px; }
.wi-legend-swatch {
  width: 18px;
  height: 2px;
  display: inline-block;
}
/* ── Chart strokes — orange bicolor palette (dashed = original, solid = cf) ── */
.wi-legend-swatch.orig {
  background: repeating-linear-gradient(
    90deg,
    rgba(10, 10, 10, 0.35) 0,
    rgba(10, 10, 10, 0.35) 4px,
    transparent 4px,
    transparent 7px
  );
}
.wi-legend-swatch.cf {
  background: var(--color-orange);
  height: 3px;
}

/* ── Impact panel — light card with subtle border, matches .lb footer feel ── */
.wi-impact {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid rgba(10,10,10,0.08);
  background: var(--color-white);
}

.wi-impact-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  gap: 12px;
}
.wi-impact-label {
  color: rgba(10,10,10,0.4);
  letter-spacing: 2px;
  text-transform: uppercase;
  font-size: 10px;
}
.wi-impact-values {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
}
.wi-val.orig { color: rgba(10,10,10,0.5); }
.wi-val.cf { color: var(--foreground); font-weight: 700; }
.wi-arrow { color: rgba(10,10,10,0.3); }

/* ── Delta pill — orange = positive shift, red = negative, neutral gray ── */
.wi-delta {
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;
  border: 1px solid transparent;
}
.wi-delta.positive {
  color: var(--color-orange);
  border-color: rgba(255, 107, 26, 0.35);
}
.wi-delta.negative {
  color: var(--color-red);
  border-color: rgba(255, 68, 68, 0.35);
}
.wi-delta.neutral {
  color: rgba(10,10,10,0.4);
  border-color: rgba(10,10,10,0.12);
}

.wi-impact-badge-row { margin-top: 4px; }
.wi-impact-badge {
  display: inline-block;
  padding: 3px 10px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  border: 1px solid transparent;
}
.wi-impact-badge.impact-strong {
  color: var(--color-orange);
  background: rgba(255, 107, 26, 0.08);
  border-color: rgba(255, 107, 26, 0.4);
}
.wi-impact-badge.impact-moderate {
  color: var(--color-amber);
  background: rgba(255, 179, 71, 0.1);
  border-color: rgba(255, 179, 71, 0.45);
}
.wi-impact-badge.impact-minimal {
  color: rgba(10,10,10,0.45);
  background: rgba(10,10,10,0.04);
  border-color: rgba(10,10,10,0.12);
}

.wi-summary {
  font-size: 11px;
  line-height: 1.55;
  color: rgba(10,10,10,0.75);
  padding-top: 8px;
  border-top: 1px solid rgba(10,10,10,0.06);
  letter-spacing: 0.2px;
}

.wi-warn {
  font-size: 10px;
  color: var(--color-orange);
  padding-top: 2px;
  letter-spacing: 1px;
}
</style>
