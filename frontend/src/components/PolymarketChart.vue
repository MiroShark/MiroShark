<template>
  <div class="pm-panel">
    <!-- Header — matches .lb-header in InfluenceLeaderboard -->
    <div class="pm-header">
      <div class="pm-header-left">
        <img src="/pm.png" alt="Polymarket" class="pm-logo" />
        <span class="pm-header-title">{{ $tr('Prediction Markets', '预测市场') }}</span>
        <span v-if="live" class="pm-live-dot"><span class="pm-live-pulse"></span>{{ $tr('LIVE', '实时') }}</span>
      </div>
      <div v-if="selected" class="pm-header-actions">
        <button
          class="pm-export-btn"
          :disabled="exporting || !copySupported"
          :title="copySupported ? $tr('Copy chart as PNG (with MiroShark watermark)', '复制图表为 PNG(含 MiroShark 水印)') : $tr('Image copy not supported in this browser', '此浏览器不支持图像复制')"
          @click="copyChart"
        >
          {{ copiedFlash ? $tr('Copied', '已复制') : $tr('Copy', '复制') }}
        </button>
        <button
          class="pm-export-btn"
          :disabled="exporting"
          :title="$tr('Download chart as PNG (with MiroShark watermark)', '下载图表为 PNG(含 MiroShark 水印)')"
          @click="downloadChart"
        >
          {{ $tr('Download ↓', '下载 ↓') }}
        </button>
      </div>
    </div>

      <!-- Body: market list (left) + chart (right) -->
      <div class="pm-body">
        <!-- Market list -->
        <aside class="pm-market-list">
          <div v-if="marketsLoading && !markets.length" class="pm-empty">{{ $tr('Loading markets...', '加载市场中...') }}</div>
          <div v-else-if="marketsError" class="pm-empty pm-error">{{ marketsError }}</div>
          <div v-else-if="!markets.length" class="pm-empty">
            <div class="pm-empty-title">{{ $tr('No markets yet', '暂无市场') }}</div>
            <div class="pm-empty-hint">{{ $tr('Markets appear as agents create them during the simulation.', '智能体在模拟过程中创建市场后,将显示在此处。') }}</div>
          </div>
          <button
            v-for="m in markets"
            :key="m.market_id"
            class="pm-market-row"
            :class="{ 'pm-market-row-active': selectedId === m.market_id }"
            @click="selectMarket(m.market_id)"
          >
            <div class="pm-market-q">{{ m.question || `${$tr('Market', '市场')} #${m.market_id}` }}</div>
            <div class="pm-market-meta">
              <span class="pm-market-price" :class="priceClass(m.price_yes)">
                {{ formatPct(m.price_yes) }}
              </span>
              <span class="pm-market-trades">{{ m.trade_count }} {{ $tr('trades', '笔交易') }}</span>
              <span v-if="m.resolved" class="pm-market-resolved">{{ m.winning_outcome || $tr('RESOLVED', '已结算') }}</span>
            </div>
          </button>
        </aside>

        <!-- Chart -->
        <section class="pm-chart-section">
          <div v-if="!selected" class="pm-placeholder">
            <div class="pm-placeholder-icon">◎</div>
            <div class="pm-placeholder-text">{{ $tr('Select a market to view its price history', '选择一个市场以查看其价格历史') }}</div>
          </div>
          <template v-else>
            <!-- Question + price header -->
            <div class="pm-chart-header">
              <div class="pm-chart-q">{{ selected.market.question || `${$tr('Market', '市场')} #${selected.market.market_id}` }}</div>
              <div class="pm-chart-price-row">
                <div class="pm-chart-price" :class="priceClass(latestPrice)">
                  {{ formatPct(latestPrice) }}
                  <span class="pm-chart-outcome-label">{{ $tr('chance', '概率') }} {{ selected.market.outcome_a || 'YES' }}</span>
                </div>
                <div v-if="priceDelta !== null" class="pm-chart-delta" :class="deltaClass(priceDelta)">
                  {{ priceDelta >= 0 ? '▲' : '▼' }} {{ formatPct(Math.abs(priceDelta)) }}
                </div>
              </div>
              <div class="pm-chart-stats">
                <span class="pm-stat"><span class="pm-stat-k">{{ $tr('TRADES', '交易') }}</span><span class="pm-stat-v">{{ selected.points.length - 1 }}</span></span>
                <span class="pm-stat"><span class="pm-stat-k">{{ $tr('VOLUME', '成交量') }}</span><span class="pm-stat-v">{{ tradeVolume.toFixed(1) }}</span></span>
                <span class="pm-stat"><span class="pm-stat-k">{{ $tr('OUTCOMES', '结果') }}</span><span class="pm-stat-v">{{ selected.market.outcome_a }}/{{ selected.market.outcome_b }}</span></span>
                <span v-if="selected.market.resolved" class="pm-stat pm-stat-resolved">{{ $tr('RESOLVED:', '已结算:') }} {{ selected.market.winning_outcome }}</span>
              </div>
            </div>

            <!-- SVG chart -->
            <div class="pm-chart-wrap">
              <svg
                ref="chartSvg"
                :viewBox="`0 0 ${W} ${H}`"
                preserveAspectRatio="none"
                class="pm-chart-svg"
                xmlns="http://www.w3.org/2000/svg"
                @mousemove="handleHover"
                @mouseleave="hoverPoint = null"
              >
                <defs>
                  <linearGradient :id="gradId" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" :stop-color="lineColor" stop-opacity="0.35" />
                    <stop offset="100%" :stop-color="lineColor" stop-opacity="0" />
                  </linearGradient>
                </defs>

                <!-- Grid lines at 0/25/50/75/100 -->
                <g v-for="pct in [0, 25, 50, 75, 100]" :key="pct">
                  <line
                    :x1="ML" :y1="yScale(pct / 100)"
                    :x2="W - MR" :y2="yScale(pct / 100)"
                    stroke="rgba(10,10,10,0.08)" stroke-width="1"
                    :stroke-dasharray="pct === 50 ? '' : '2,3'"
                  />
                  <text
                    :x="W - MR + 8" :y="yScale(pct / 100) + 4"
                    fill="rgba(10,10,10,0.45)" font-size="10"
                    font-family="'Space Mono', ui-monospace, monospace"
                  >{{ pct }}%</text>
                </g>

                <!-- Area fill -->
                <path v-if="hasPath" :d="areaPath" :fill="`url(#${gradId})`" />

                <!-- Line -->
                <path
                  v-if="hasPath"
                  :d="linePath"
                  fill="none"
                  :stroke="lineColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />

                <!-- Latest point dot -->
                <circle
                  v-if="hasPath"
                  :cx="xScale(selected.points.length - 1)"
                  :cy="yScale(latestPrice)"
                  r="4"
                  :fill="lineColor"
                />
                <circle
                  v-if="hasPath"
                  :cx="xScale(selected.points.length - 1)"
                  :cy="yScale(latestPrice)"
                  r="8"
                  :fill="lineColor"
                  fill-opacity="0.2"
                />

                <!-- Hover crosshair + tooltip -->
                <g v-if="hoverPoint !== null && hasPath">
                  <line
                    :x1="xScale(hoverPoint)" :y1="MT"
                    :x2="xScale(hoverPoint)" :y2="H - MB"
                    stroke="rgba(10,10,10,0.25)" stroke-width="1" stroke-dasharray="2,3"
                  />
                  <circle
                    :cx="xScale(hoverPoint)"
                    :cy="yScale(selected.points[hoverPoint].price_yes)"
                    r="4"
                    :fill="lineColor"
                    stroke="#FAFAFA" stroke-width="2"
                  />
                </g>
              </svg>

              <!-- Hover tooltip -->
              <div v-if="hoverPoint !== null && hoverTooltipStyle" class="pm-tooltip" :style="hoverTooltipStyle">
                <div class="pm-tooltip-price" :class="priceClass(selected.points[hoverPoint].price_yes)">
                  {{ formatPct(selected.points[hoverPoint].price_yes) }}
                </div>
                <div v-if="selected.points[hoverPoint].side" class="pm-tooltip-trade">
                  {{ selected.points[hoverPoint].side.toUpperCase() }}
                  {{ selected.points[hoverPoint].outcome }}
                  · {{ selected.points[hoverPoint].shares?.toFixed(1) }} shares
                </div>
                <div v-else class="pm-tooltip-trade">{{ $tr('Origin (no trades yet)', '初始(尚无交易)') }}</div>
                <div class="pm-tooltip-time">{{ formatTime(selected.points[hoverPoint].t) }}</div>
              </div>
            </div>
          </template>
        </section>
      </div>
    </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { getPolymarketMarkets, getPolymarketMarketPrices } from '../api/simulation'
import {
  renderSvgToCanvas,
  downloadCanvas,
  copyCanvasToClipboard,
  canCopyImageToClipboard,
  wrapText,
} from '../utils/chartExport'
import { tr } from '../i18n'

const props = defineProps({
  simulationId: { type: String, required: true },
  visible: { type: Boolean, default: false },
  live: { type: Boolean, default: false },
})

const W = 900
const H = 360
const ML = 16
const MR = 44
const MT = 16
const MB = 24

const markets = ref([])
const marketsLoading = ref(false)
const marketsError = ref('')
const selectedId = ref(null)
const selected = ref(null)
const selectedError = ref('')
const pollTimer = ref(null)
const hoverPoint = ref(null)
const hoverTooltipStyle = ref(null)
const chartSvg = ref(null)
const exporting = ref(false)
const copiedFlash = ref(false)
let copiedFlashTimer = null
const copySupported = canCopyImageToClipboard()

const gradId = computed(() => `pm-grad-${selectedId.value ?? 'x'}`)

const latestPrice = computed(() => {
  if (!selected.value?.points?.length) return 0.5
  return selected.value.points[selected.value.points.length - 1].price_yes
})

const priceDelta = computed(() => {
  const pts = selected.value?.points
  if (!pts || pts.length < 2) return null
  return pts[pts.length - 1].price_yes - pts[0].price_yes
})

const lineColor = computed(() => {
  const p = latestPrice.value
  if (p >= 0.55) return '#43C165'
  if (p <= 0.45) return '#FF4444'
  return '#FF6B1A'
})

const tradeVolume = computed(() => {
  const pts = selected.value?.points || []
  return pts.reduce((sum, p) => sum + (p.shares || 0), 0)
})

const xScale = (i) => {
  const pts = selected.value?.points || []
  if (pts.length <= 1) return ML
  const w = W - ML - MR
  return ML + (i / (pts.length - 1)) * w
}

const yScale = (price) => {
  const h = H - MT - MB
  return MT + (1 - price) * h
}

const hasPath = computed(() => (selected.value?.points?.length || 0) >= 2)

const linePath = computed(() => {
  const pts = selected.value?.points || []
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${xScale(i).toFixed(2)},${yScale(p.price_yes).toFixed(2)}`).join(' ')
})

const areaPath = computed(() => {
  const pts = selected.value?.points || []
  if (pts.length < 2) return ''
  const top = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${xScale(i).toFixed(2)},${yScale(p.price_yes).toFixed(2)}`).join(' ')
  const baseY = (H - MB).toFixed(2)
  return `${top} L${xScale(pts.length - 1).toFixed(2)},${baseY} L${xScale(0).toFixed(2)},${baseY} Z`
})

function formatPct(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return `${(v * 100).toFixed(1)}%`
}

function priceClass(p) {
  if (p >= 0.55) return 'pm-up'
  if (p <= 0.45) return 'pm-down'
  return 'pm-neutral'
}

function deltaClass(d) {
  if (d > 0.005) return 'pm-up'
  if (d < -0.005) return 'pm-down'
  return 'pm-neutral'
}

function formatTime(t) {
  if (!t) return ''
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return String(t)
  return d.toLocaleString()
}

async function fetchMarkets({ autoSelect = false } = {}) {
  if (!props.simulationId) return
  marketsLoading.value = true
  marketsError.value = ''
  try {
    const res = await getPolymarketMarkets(props.simulationId)
    const data = res?.data?.data || res?.data || {}
    markets.value = Array.isArray(data.markets) ? data.markets : []
    if (autoSelect && markets.value.length && selectedId.value === null) {
      const topMarket = [...markets.value].sort((a, b) => (b.trade_count || 0) - (a.trade_count || 0))[0]
      selectedId.value = topMarket.market_id
    }
  } catch (err) {
    marketsError.value = err?.response?.data?.error || err?.message || tr('Failed to load markets', '加载市场失败')
  } finally {
    marketsLoading.value = false
  }
}

async function fetchSelected() {
  if (!props.simulationId || selectedId.value === null) return
  try {
    const res = await getPolymarketMarketPrices(props.simulationId, selectedId.value)
    const payload = res?.data?.data || res?.data
    if (payload?.market) {
      selected.value = payload
      selectedError.value = ''
    }
  } catch (err) {
    selectedError.value = err?.response?.data?.error || err?.message || tr('Failed to load prices', '加载价格失败')
  }
}

function selectMarket(id) {
  selectedId.value = id
  selected.value = null
  hoverPoint.value = null
  fetchSelected()
}

function startPolling() {
  if (pollTimer.value) clearInterval(pollTimer.value)
  pollTimer.value = setInterval(async () => {
    await fetchMarkets()
    if (selectedId.value !== null) await fetchSelected()
  }, props.live ? 4000 : 20000)
}

function handleHover(event) {
  const pts = selected.value?.points || []
  if (!pts.length) {
    hoverPoint.value = null
    hoverTooltipStyle.value = null
    return
  }
  const rect = event.currentTarget.getBoundingClientRect()
  const relX = (event.clientX - rect.left) / rect.width
  const svgX = relX * W
  const clamped = Math.max(ML, Math.min(W - MR, svgX))
  const frac = (clamped - ML) / (W - ML - MR)
  const idx = Math.round(frac * (pts.length - 1))
  hoverPoint.value = Math.max(0, Math.min(pts.length - 1, idx))

  const tx = (xScale(hoverPoint.value) / W) * rect.width
  const ty = (yScale(pts[hoverPoint.value].price_yes) / H) * rect.height
  const leftSide = tx > rect.width / 2
  hoverTooltipStyle.value = {
    left: leftSide ? `${tx - 160}px` : `${tx + 12}px`,
    top: `${Math.max(8, ty - 60)}px`,
  }
}

// ── Chart export (copy + download as PNG, with MiroShark watermark) ──

const PX = 32 // header horizontal padding

// Colour matching `priceClass` / `deltaClass` used in the live panel.
const _priceColor = (p) => {
  if (p >= 0.55) return '#43C165'
  if (p <= 0.45) return '#FF4444'
  return '#FF6B1A'
}

const _buildExportCanvas = async () => {
  if (!chartSvg.value || !selected.value) {
    throw new Error('No chart to export')
  }
  const m = selected.value.market
  const pts = selected.value.points || []
  const question = m.question || `Market #${m.market_id}`
  const priceVal = latestPrice.value
  const priceColor = _priceColor(priceVal)
  const priceStr = `${(priceVal * 100).toFixed(1)}%`
  const outcomeLabel = (m.outcome_a || 'YES').toUpperCase()
  const delta = priceDelta.value
  const deltaStr = delta != null ? `${delta >= 0 ? '▲' : '▼'} ${(Math.abs(delta) * 100).toFixed(1)}%` : null
  const deltaColor = delta == null
    ? null
    : (delta > 0.005 ? '#43C165' : (delta < -0.005 ? '#FF4444' : '#FF6B1A'))

  const stats = [
    { k: 'TRADES', v: String(Math.max(pts.length - 1, 0)) },
    { k: 'VOLUME', v: tradeVolume.value.toFixed(1) },
    { k: 'OUTCOMES', v: `${m.outcome_a || 'YES'}/${m.outcome_b || 'NO'}` },
  ]
  if (m.resolved) stats.push({ k: 'RESOLVED', v: m.winning_outcome || 'YES' })

  // ── Measure title height so the header sizes to its content ──
  // Fonts: Young Serif 44px for the title, Space Mono for everything else.
  const titleFont = '700 44px "Young Serif", Georgia, serif'
  const titleLineHeight = 54
  const measureCanvas = document.createElement('canvas')
  const measureCtx = measureCanvas.getContext('2d')
  measureCtx.font = titleFont
  const titleLines = wrapText(measureCtx, question, W - PX * 2)

  // Layout: 36 (top) + title + 22 (gap) + 60 (price row) + 18 (gap) + 42 (stats) + 28 (bottom)
  const titleBlock = titleLines.length * titleLineHeight
  const headerHeight = 36 + titleBlock + 22 + 60 + 18 + 42 + 28

  const drawHeader = (ctx) => {
    let y = 36

    // ── Title ── Young Serif, largest element
    ctx.fillStyle = '#0A0A0A'
    ctx.font = titleFont
    ctx.textAlign = 'left'
    ctx.textBaseline = 'top'
    for (const line of titleLines) {
      ctx.fillText(line, PX, y)
      y += titleLineHeight
    }
    y += 22 - (titleLineHeight - 44) // tighten after last baseline

    // ── Big orange price ──
    ctx.fillStyle = priceColor
    ctx.font = '700 56px "Space Mono", "JetBrains Mono", ui-monospace, monospace'
    ctx.textBaseline = 'alphabetic'
    const priceBaseline = y + 46
    ctx.fillText(priceStr, PX, priceBaseline)
    const priceWidth = ctx.measureText(priceStr).width

    // "CHANCE YES" label next to the price
    ctx.fillStyle = 'rgba(10, 10, 10, 0.5)'
    ctx.font = '400 13px "Space Mono", "JetBrains Mono", ui-monospace, monospace'
    ctx.fillText(`CHANCE ${outcomeLabel}`, PX + priceWidth + 18, priceBaseline - 4)

    // Delta pill, right-aligned to keep from colliding with the label
    if (deltaStr) {
      ctx.font = '700 15px "Space Mono", "JetBrains Mono", ui-monospace, monospace'
      const dw = ctx.measureText(deltaStr).width + 24
      const dh = 32
      const dx = W - PX - dw
      const dy = priceBaseline - 34
      // Tinted background (12% opacity of the delta colour)
      ctx.fillStyle = deltaColor + '1f' // 1f = ~12% alpha
      ctx.fillRect(dx, dy, dw, dh)
      ctx.fillStyle = deltaColor
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(deltaStr, dx + dw / 2, dy + dh / 2)
      ctx.textAlign = 'left'
    }

    y = priceBaseline + 14 + 18 // below the price baseline, gap

    // ── Stats row ──
    const colW = (W - PX * 2) / stats.length
    stats.forEach((s, i) => {
      const cx = PX + i * colW
      // Label (uppercase small)
      ctx.fillStyle = 'rgba(10, 10, 10, 0.45)'
      ctx.font = '700 10px "Space Mono", "JetBrains Mono", ui-monospace, monospace'
      ctx.textAlign = 'left'
      ctx.textBaseline = 'top'
      ctx.fillText(s.k, cx, y)
      // Value
      ctx.fillStyle = '#0A0A0A'
      ctx.font = '700 14px "Space Mono", "JetBrains Mono", ui-monospace, monospace'
      ctx.fillText(s.v, cx, y + 16)
    })
  }

  return renderSvgToCanvas(chartSvg.value, {
    width: W,
    height: H,
    scale: 2,
    headerHeight,
    drawHeader,
    subtitle: `${props.simulationId || 'simulation'} · ${new Date().toLocaleDateString()}`,
  })
}

const _flashCopied = () => {
  copiedFlash.value = true
  if (copiedFlashTimer) clearTimeout(copiedFlashTimer)
  copiedFlashTimer = setTimeout(() => { copiedFlash.value = false }, 1600)
}

async function copyChart() {
  if (exporting.value) return
  exporting.value = true
  try {
    const canvas = await _buildExportCanvas()
    await copyCanvasToClipboard(canvas)
    _flashCopied()
  } catch (err) {
    // Fall back to download so the user doesn't lose the image
    console.warn('[markets] copy failed, falling back to download:', err)
    try {
      const canvas = await _buildExportCanvas()
      const fname = `markets-${selected.value?.market?.market_id ?? 'x'}-${props.simulationId || 'sim'}.png`
      downloadCanvas(canvas, fname)
    } catch (err2) {
      console.error('[markets] download fallback failed:', err2)
    }
  } finally {
    exporting.value = false
  }
}

async function downloadChart() {
  if (exporting.value) return
  exporting.value = true
  try {
    const canvas = await _buildExportCanvas()
    const marketId = selected.value?.market?.market_id ?? 'x'
    const fname = `miroshark-market-${marketId}-${props.simulationId || 'sim'}.png`
    downloadCanvas(canvas, fname)
  } catch (err) {
    console.error('[markets] download failed:', err)
  } finally {
    exporting.value = false
  }
}

// Parent uses v-if, so the component only exists while the overlay is visible.
// Kick off polling on mount; stop it on unmount.
const start = async () => {
  hoverPoint.value = null
  selected.value = null
  selectedId.value = null
  await fetchMarkets({ autoSelect: true })
  if (selectedId.value !== null) await fetchSelected()
  startPolling()
}

watch(() => props.simulationId, () => {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
  start()
})

watch(() => props.live, () => {
  if (pollTimer.value) startPolling()
})

onMounted(() => { start() })

onBeforeUnmount(() => {
  if (pollTimer.value) clearInterval(pollTimer.value)
  if (copiedFlashTimer) clearTimeout(copiedFlashTimer)
})
</script>

<style scoped>
/* MiroShark-native Polymarket panel — renders inline inside the parent
   .influence-overlay, matching the other toolbar overlays (Influence/Drift/
   Network/Demographics/What If?/Branch). No fixed positioning, no modal. */

.pm-panel {
  width: 100%;
  height: 100%;
  background: var(--background);
  color: var(--foreground);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-family: var(--font-mono);
}

/* ── Header — mirrors .lb-header ── */
.pm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(10, 10, 10, 0.08);
  flex-shrink: 0;
}

.pm-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* Header action cluster — mirrors .export-btn in InfluenceLeaderboard */
.pm-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pm-export-btn {
  background: none;
  border: 1px solid rgba(10, 10, 10, 0.15);
  color: rgba(10, 10, 10, 0.5);
  padding: 4px 10px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 1px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.pm-export-btn:hover:not(:disabled) {
  border-color: var(--color-orange);
  color: var(--color-orange);
}

.pm-export-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.pm-logo {
  width: 14px;
  height: 14px;
  border-radius: 2px;
}

.pm-header-title {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: rgba(10, 10, 10, 0.5);
}

.pm-live-dot {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  background: transparent;
  border: 1px solid var(--color-orange);
  color: var(--color-orange);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 2px;
  font-weight: 700;
  margin-left: 8px;
  text-transform: uppercase;
}

.pm-live-pulse {
  width: 6px;
  height: 6px;
  background: var(--color-orange);
  border-radius: 50%;
  animation: pm-pulse 1.4s ease-in-out infinite;
}

@keyframes pm-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.3; transform: scale(1.3); }
}

.pm-body {
  flex: 1;
  display: grid;
  grid-template-columns: 320px 1fr;
  overflow: hidden;
}

/* Market list — subtler separator, rows match .lb-row treatment */
.pm-market-list {
  border-right: 1px solid rgba(10, 10, 10, 0.08);
  overflow-y: auto;
  padding: 0;
  background: var(--background);
}

.pm-market-row {
  width: 100%;
  text-align: left;
  background: transparent;
  border: none;
  border-bottom: 1px solid rgba(10, 10, 10, 0.04);
  border-left: 3px solid transparent;
  padding: 10px 14px;
  cursor: pointer;
  color: inherit;
  font-family: var(--font-mono);
  transition: background 0.1s ease;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pm-market-row:hover {
  background: rgba(10, 10, 10, 0.02);
}

/* Active row — same orange left-accent pattern as .lb-row.top-three */
.pm-market-row-active {
  background: rgba(10, 10, 10, 0.02);
  border-left-color: var(--color-orange);
}

.pm-market-q {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.4;
  color: var(--color-black);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.pm-market-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 11px;
  font-family: var(--font-mono);
}

.pm-market-price {
  font-weight: 700;
  font-size: 13px;
  letter-spacing: 0.5px;
}

.pm-up { color: var(--color-green); }
.pm-down { color: var(--color-red); }
.pm-neutral { color: var(--color-orange); }

.pm-market-trades {
  color: rgba(10, 10, 10, 0.5);
  font-size: 10px;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.pm-market-resolved {
  margin-left: auto;
  padding: 2px 6px;
  background: var(--color-black);
  color: var(--color-white);
  font-size: 9px;
  letter-spacing: 1px;
  border-radius: 0;
  text-transform: uppercase;
}

.pm-empty {
  padding: 36px 20px;
  text-align: center;
  color: rgba(10, 10, 10, 0.55);
  font-family: var(--font-mono);
  font-size: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pm-empty-title {
  color: var(--color-black);
  font-weight: 700;
  font-size: 12px;
  letter-spacing: 2px;
  text-transform: uppercase;
}

.pm-empty-hint {
  font-size: 11px;
  color: rgba(10, 10, 10, 0.5);
  line-height: 1.5;
}

.pm-error {
  color: var(--color-red);
}

/* Chart section */
.pm-chart-section {
  padding: 20px 24px 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: var(--color-white);
}

.pm-placeholder {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: rgba(10, 10, 10, 0.35);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
}

.pm-placeholder-icon {
  font-size: 36px;
  color: var(--color-orange);
  opacity: 0.4;
}

.pm-chart-header {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(10, 10, 10, 0.12);
}

.pm-chart-q {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 400;
  line-height: 1.25;
  color: var(--color-black);
}

.pm-chart-price-row {
  display: flex;
  align-items: baseline;
  gap: 14px;
}

.pm-chart-price {
  font-family: var(--font-mono);
  font-size: 40px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.01em;
}

.pm-chart-outcome-label {
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10, 10, 10, 0.5);
  margin-left: 10px;
  letter-spacing: 2px;
  text-transform: uppercase;
}

.pm-chart-delta {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
  padding: 3px 8px;
  border-radius: 0;
}

.pm-chart-delta.pm-up {
  background: rgba(67, 193, 101, 0.12);
}

.pm-chart-delta.pm-down {
  background: rgba(255, 68, 68, 0.12);
}

.pm-chart-delta.pm-neutral {
  background: rgba(255, 107, 26, 0.12);
}

.pm-chart-stats {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
  margin-top: 6px;
  font-family: var(--font-mono);
}

.pm-stat {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.pm-stat-k {
  font-size: 9px;
  letter-spacing: 2px;
  color: rgba(10, 10, 10, 0.45);
  font-weight: 700;
  text-transform: uppercase;
}

.pm-stat-v {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--color-black);
  font-weight: 700;
}

.pm-stat-resolved {
  padding: 6px 10px;
  background: var(--color-green);
  color: var(--color-white);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  border-radius: 0;
  align-self: center;
  text-transform: uppercase;
}

.pm-chart-wrap {
  flex: 1;
  min-height: 320px;
  position: relative;
  background: rgba(10, 10, 10, 0.02);
  border: 1px solid rgba(10, 10, 10, 0.06);
  padding: 4px;
}

.pm-chart-svg {
  width: 100%;
  height: 100%;
  display: block;
}

/* Tooltip — flat light card, no offset-drop-shadow (matches the rest of the
   design system which uses subtle 1px borders instead). */
.pm-tooltip {
  position: absolute;
  min-width: 150px;
  padding: 8px 10px;
  background: var(--color-white);
  border: 1px solid rgba(10, 10, 10, 0.12);
  pointer-events: none;
  z-index: 5;
  font-family: var(--font-mono);
}

.pm-tooltip-price {
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0.5px;
}

.pm-tooltip-trade {
  font-size: 10px;
  color: rgba(10, 10, 10, 0.65);
  margin-top: 4px;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.pm-tooltip-time {
  font-size: 10px;
  color: rgba(10, 10, 10, 0.45);
  margin-top: 2px;
  font-family: var(--font-mono);
}

/* Scrollbar in light theme */
.pm-market-list::-webkit-scrollbar,
.pm-chart-section::-webkit-scrollbar {
  width: 10px;
}
.pm-market-list::-webkit-scrollbar-track,
.pm-chart-section::-webkit-scrollbar-track {
  background: var(--color-gray);
}
.pm-market-list::-webkit-scrollbar-thumb,
.pm-chart-section::-webkit-scrollbar-thumb {
  background: rgba(10, 10, 10, 0.2);
}
</style>
