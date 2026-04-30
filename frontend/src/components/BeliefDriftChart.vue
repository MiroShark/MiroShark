<template>
  <div class="belief-drift">
    <!-- Header -->
    <div class="bd-header">
      <div class="bd-title">
        <span class="bd-icon">◎</span>
        <span class="bd-label">{{ $tr('DRIFT', '漂移') }}</span>
      </div>
      <div class="bd-header-actions">
        <button
          class="bd-export-btn"
          :disabled="!hasData || exporting || !copySupported"
          :title="copySupported ? $tr('Copy chart as PNG (with MiroShark watermark)', '复制图表为 PNG(含 MiroShark 水印)') : $tr('Image copy not supported in this browser', '此浏览器不支持图像复制')"
          @click="copyChart"
        >
          {{ copiedFlash ? $tr('Copied', '已复制') : $tr('Copy', '复制') }}
        </button>
        <button
          class="bd-export-btn"
          :disabled="!hasData || exporting"
          @click="downloadChart"
          :title="$tr('Download chart as PNG (with MiroShark watermark)', '下载图表为 PNG(含 MiroShark 水印)')"
        >
          {{ $tr('Download ↓', '下载 ↓') }}
        </button>
      </div>
    </div>

    <!-- Legend -->
    <div class="bd-legend">
      <span class="legend-item"><span class="legend-dot bullish-dot"></span>{{ $tr('Bullish', '看涨') }} (&gt;+0.2)</span>
      <span class="legend-item"><span class="legend-dot neutral-dot"></span>{{ $tr('Neutral', '中立') }}</span>
      <span class="legend-item"><span class="legend-dot bearish-dot"></span>{{ $tr('Bearish', '看跌') }} (&lt;-0.2)</span>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="bd-state">
      <div class="pulse-ring"></div>
      <span>{{ $tr('Computing belief drift...', '计算信念漂移中...') }}</span>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="bd-state bd-error-state">{{ error }}</div>

    <!-- No trajectory data -->
    <div v-else-if="!hasData" class="bd-state">
      <span>{{ $tr('No belief trajectory data available.', '暂无信念轨迹数据。') }}</span>
      <span class="bd-hint">{{ $tr('Run a simulation with belief tracking enabled.', '请启用信念追踪运行模拟。') }}</span>
    </div>

    <!-- Chart -->
    <div v-else class="bd-chart-wrap">
      <svg
        :viewBox="`0 0 ${W} ${H}`"
        preserveAspectRatio="xMidYMid meet"
        class="bd-svg"
        ref="svgRef"
        xmlns="http://www.w3.org/2000/svg"
      >
        <!-- Horizontal grid lines + Y labels -->
        <g v-for="pct in [0, 25, 50, 75, 100]" :key="pct">
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

        <!-- Stacked area: bearish (bottom layer, coral) -->
        <path
          :d="bearishPath"
          fill="rgba(239,68,68,0.55)"
          stroke="rgba(239,68,68,0.8)"
          stroke-width="1"
        />

        <!-- Stacked area: neutral (middle, slate) -->
        <path
          :d="neutralPath"
          fill="rgba(148,163,184,0.55)"
          stroke="rgba(148,163,184,0.8)"
          stroke-width="1"
        />

        <!-- Stacked area: bullish (top, teal) -->
        <path
          :d="bullishPath"
          fill="rgba(20,184,166,0.55)"
          stroke="rgba(20,184,166,0.8)"
          stroke-width="1"
        />

        <!-- Consensus vertical line -->
        <line
          v-if="driftData.consensus_round != null"
          :x1="xS(driftData.consensus_round)" :y1="MT"
          :x2="xS(driftData.consensus_round)" :y2="H - MB"
          stroke="rgba(10,10,10,0.5)" stroke-width="1.5"
          stroke-dasharray="4,3"
        />
        <text
          v-if="driftData.consensus_round != null"
          :x="xS(driftData.consensus_round) + 4" :y="MT + 12"
          fill="rgba(10,10,10,0.5)" font-size="9" font-family="monospace"
        >{{ $tr('consensus r', '共识 r') }}{{ driftData.consensus_round }}</text>

        <!-- Director event injection markers -->
        <g v-for="(evt, idx) in eventMarkers" :key="'evt' + idx">
          <line
            :x1="xS(evt.round)" :y1="MT"
            :x2="xS(evt.round)" :y2="H - MB"
            stroke="rgba(245,158,11,0.7)" stroke-width="1.5"
            stroke-dasharray="3,2"
          />
          <text
            :x="xS(evt.round) + 4"
            :y="MT + 12 + idx * 11"
            fill="rgba(245,158,11,0.8)" font-size="8" font-family="monospace"
          >⚡ r{{ evt.round }}</text>
        </g>

        <!-- X axis labels -->
        <text
          v-for="r in xTicks"
          :key="'xt' + r"
          :x="xS(r)" :y="H - MB + 13"
          fill="rgba(10,10,10,0.35)" font-size="9"
          font-family="monospace" text-anchor="middle"
        >{{ r }}</text>

        <!-- X axis title -->
        <text
          :x="ML + (W - ML - MR) / 2" :y="H - 2"
          fill="rgba(10,10,10,0.3)" font-size="9"
          font-family="monospace" text-anchor="middle"
        >{{ $tr('Round', '轮次') }}</text>
      </svg>
    </div>

    <!-- Summary line -->
    <div v-if="driftData?.summary" class="bd-summary">
      {{ driftData.summary }}
    </div>

    <!-- Topics footer -->
    <div v-if="driftData?.topics?.length" class="bd-topics">
      {{ $tr('Topics:', '话题:') }} {{ driftData.topics.join(' · ') }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { getBeliefDrift } from '../api/simulation'
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
  visible: { type: Boolean, default: false },
  directorEvents: { type: Array, default: () => [] }
})

const loading = ref(false)
const error = ref('')
const driftData = ref(null)
const svgRef = ref(null)
const exporting = ref(false)
const copiedFlash = ref(false)
let copiedFlashTimer = null
const copySupported = canCopyImageToClipboard()

// SVG dimensions and margins
const W = 560
const H = 200
const MT = 14  // margin top
const MB = 26  // margin bottom
const ML = 34  // margin left
const MR = 12  // margin right

const hasData = computed(() =>
  driftData.value?.rounds?.length > 0
)

const minR = computed(() => hasData.value ? driftData.value.rounds[0] : 1)
const maxR = computed(() => hasData.value ? driftData.value.rounds[driftData.value.rounds.length - 1] : 10)

const xS = (r) => {
  const span = Math.max(maxR.value - minR.value, 1)
  return ML + ((r - minR.value) / span) * (W - ML - MR)
}

const yS = (pct) => {
  return MT + (1 - pct / 100) * (H - MT - MB)
}

const xTicks = computed(() => {
  if (!hasData.value) return []
  const rounds = driftData.value.rounds
  if (rounds.length <= 10) return rounds
  const step = Math.ceil(rounds.length / 10)
  return rounds.filter((_, i) => i % step === 0 || i === rounds.length - 1)
})

// Build a closed SVG area path between topPcts and botPcts arrays
const areaPath = (topPcts, botPcts, rounds) => {
  if (!rounds.length) return ''
  const top = rounds.map((r, i) => `${i === 0 ? 'M' : 'L'}${xS(r).toFixed(1)},${yS(topPcts[i]).toFixed(1)}`).join(' ')
  const bot = rounds.slice().reverse().map((r, i) => {
    const orig = rounds.length - 1 - i
    return `L${xS(r).toFixed(1)},${yS(botPcts[orig]).toFixed(1)}`
  }).join(' ')
  return `${top} ${bot} Z`
}

const bearishPath = computed(() => {
  if (!hasData.value) return ''
  const { rounds, bearish } = driftData.value
  return areaPath(bearish, bearish.map(() => 0), rounds)
})

const neutralPath = computed(() => {
  if (!hasData.value) return ''
  const { rounds, bearish, neutral } = driftData.value
  const top = bearish.map((b, i) => b + neutral[i])
  return areaPath(top, bearish, rounds)
})

const bullishPath = computed(() => {
  if (!hasData.value) return ''
  const { rounds, bearish, neutral, bullish } = driftData.value
  const bot = bearish.map((b, i) => b + neutral[i])
  const top = bot.map((b, i) => b + bullish[i])
  return areaPath(top, bot, rounds)
})

const eventMarkers = computed(() => {
  if (!hasData.value || !props.directorEvents?.length) return []
  return props.directorEvents
    .filter(e => e.injected_at_round != null)
    .map(e => ({ round: e.injected_at_round, text: e.event_text }))
})

const load = async () => {
  if (!props.simulationId) return
  loading.value = true
  error.value = ''
  try {
    const res = await getBeliefDrift(props.simulationId)
    if (res.success && res.data) {
      driftData.value = res.data
    } else if (res.success && !res.data) {
      driftData.value = null
    } else {
      error.value = res.error || tr('Failed to load belief drift data.', '加载信念漂移数据失败。')
    }
  } catch (err) {
    error.value = err.message || tr('Failed to load belief drift.', '加载信念漂移失败。')
  } finally {
    loading.value = false
  }
}

// ── Chart export (copy + download, with MiroShark watermark) ──

const _buildExportCanvas = () => {
  if (!svgRef.value || !hasData.value) throw new Error('No chart to export')
  const d = driftData.value || {}
  const bullish = d.bullish || []
  const bearish = d.bearish || []
  const parts = []
  if (bullish.length) parts.push(`${bullish[bullish.length - 1]}% ${tr('bullish', '看涨')}`)
  if (bearish.length) parts.push(`${bearish[bearish.length - 1]}% ${tr('bearish', '看跌')}`)
  const { drawHeader, headerHeight } = buildTitledHeader({
    title: tr('Belief drift — bullish / neutral / bearish', '信念漂移 — 看涨 / 中立 / 看跌'),
    subtitle: parts.length ? `${tr('Final:', '最终:')} ${parts.join(' · ')}` : null,
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
  if (exporting.value || !hasData.value) return
  exporting.value = true
  try {
    const canvas = await _buildExportCanvas()
    await copyCanvasToClipboard(canvas)
    _flashCopied()
  } catch (err) {
    console.warn('[drift] copy failed, falling back to download:', err)
    try {
      const canvas = await _buildExportCanvas()
      downloadCanvas(canvas, `miroshark-drift-${props.simulationId}.png`)
    } catch (err2) {
      console.error('[drift] download fallback failed:', err2)
    }
  } finally {
    exporting.value = false
  }
}

async function downloadChart() {
  if (exporting.value || !hasData.value) return
  exporting.value = true
  try {
    const canvas = await _buildExportCanvas()
    downloadCanvas(canvas, `miroshark-drift-${props.simulationId}.png`)
  } catch (err) {
    console.error('[drift] download failed:', err)
  } finally {
    exporting.value = false
  }
}

watch(() => props.visible, (val) => { if (val) load() })
watch(() => props.simulationId, () => { if (props.visible) load() })
onMounted(() => { if (props.visible) load() })
onBeforeUnmount(() => {
  if (copiedFlashTimer) clearTimeout(copiedFlashTimer)
})
</script>

<style scoped>
.belief-drift {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  font-family: var(--font-mono);
  background: var(--background);
}

/* Header */
.bd-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.08);
  flex-shrink: 0;
}

.bd-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bd-icon {
  color: #14b8a6;
  font-size: 14px;
}

.bd-label {
  font-size: 12px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.5);
}

.bd-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bd-export-btn {
  background: none;
  border: 1px solid rgba(10,10,10,0.15);
  padding: 4px 10px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 1px;
  cursor: pointer;
  color: rgba(10,10,10,0.5);
  transition: all 0.15s ease;
}

.bd-export-btn:hover:not(:disabled) {
  border-color: var(--color-orange);
  color: var(--color-orange);
}

.bd-export-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* Legend */
.bd-legend {
  display: flex;
  gap: 16px;
  padding: 8px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.05);
  flex-shrink: 0;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: rgba(10,10,10,0.35);
  letter-spacing: 1px;
}

.legend-dot {
  width: 8px;
  height: 8px;
}

.bullish-dot { background: rgba(20,184,166,0.7); }
.neutral-dot  { background: rgba(148,163,184,0.7); }
.bearish-dot  { background: rgba(239,68,68,0.7); }

/* States */
.bd-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 8px;
  padding: 40px;
  font-size: 13px;
  color: rgba(10,10,10,0.35);
  letter-spacing: 1px;
  text-align: center;
}

.bd-error-state { color: #dc2626; }

.bd-hint {
  font-size: 11px;
  color: rgba(10,10,10,0.25);
}

.pulse-ring {
  width: 20px;
  height: 20px;
  border: 2px solid #14b8a6;
  border-radius: 50%;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50%       { transform: scale(1.4); opacity: 0.4; }
}

/* Chart */
.bd-chart-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  min-height: 0;
}

.bd-svg {
  width: 100%;
  height: 100%;
  max-height: 220px;
  overflow: visible;
}

/* Summary */
.bd-summary {
  padding: 10px 16px 4px;
  font-size: 12px;
  color: rgba(10,10,10,0.55);
  letter-spacing: 0.5px;
  line-height: 1.5;
  border-top: 1px solid rgba(10,10,10,0.05);
  flex-shrink: 0;
}

/* Topics */
.bd-topics {
  padding: 4px 16px 10px;
  font-size: 10px;
  color: rgba(10,10,10,0.3);
  letter-spacing: 1px;
  flex-shrink: 0;
}
</style>
