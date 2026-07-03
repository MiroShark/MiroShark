<template>
  <div
    class="embed-widget"
    :class="[themeClass, { 'chart-only': chartOnly, 'compact': isCompact }]"
  >
    <div v-if="loading" class="embed-state">
      <div class="embed-spinner"></div>
      <span>{{ $tr('Loading simulation…', '加载模拟中…', { de: 'Simulation wird geladen…', fr: 'Chargement de la simulation…' }) }}</span>
    </div>

    <div v-else-if="error" class="embed-state embed-error">
      <span>{{ error }}</span>
      <a class="embed-footer-link" :href="simulationUrl" target="_blank" rel="noopener">
        {{ $tr('Open on MiroShark ↗', '在 MiroShark 中打开 ↗', { de: 'In MiroShark öffnen ↗', fr: 'Ouvrir sur MiroShark ↗' }) }}
      </a>
    </div>

    <template v-else>
      <header v-if="!chartOnly" class="embed-header">
        <div class="embed-scenario" :title="summary.scenario">{{ scenarioTitle }}</div>
        <div class="embed-meta">
          <span class="embed-pill status" :class="statusClass">{{ statusLabel }}</span>
          <span v-if="hasRounds" class="embed-pill">
            {{ $tr('Round', '轮次', { de: 'Runde', fr: 'Tour' }) }} {{ summary.current_round }}/{{ summary.total_rounds || summary.current_round }}
          </span>
          <span class="embed-pill">{{ summary.profiles_count || 0 }} {{ $tr('agents', '智能体', { de: 'Agenten', fr: 'agents' }) }}</span>
          <span
            v-if="costLabel"
            class="embed-pill cost"
            :title="$tr('Estimated cost to run this simulation (lower bound, from logged LLM calls)', '运行此模拟的预估成本(基于已记录的 LLM 调用,为下限)', { de: 'Geschätzte Kosten für diese Simulation (Untergrenze, aus protokollierten LLM-Aufrufen)', fr: 'Coût estimé pour cette simulation (borne basse, depuis les appels LLM loggés)' })"
          >
            {{ costLabel }}
          </span>
          <span v-if="summary.quality && summary.quality.health" class="embed-pill quality" :class="qualityClass">
            {{ summary.quality.health }}
          </span>
        </div>
      </header>

      <div class="embed-chart-wrap">
        <svg
          v-if="hasBelief"
          class="embed-chart"
          :viewBox="`0 0 ${CHART_W} ${CHART_H}`"
          preserveAspectRatio="none"
          xmlns="http://www.w3.org/2000/svg"
          role="img"
          :aria-label="chartAriaLabel"
        >
          <path :d="bullishPath" fill="var(--bullish)" opacity="0.85" />
          <path :d="neutralPath" fill="var(--neutral)" opacity="0.85" />
          <path :d="bearishPath" fill="var(--bearish)" opacity="0.85" />
          <line
            v-if="consensusX !== null"
            :x1="consensusX" :x2="consensusX"
            :y1="0" :y2="CHART_H"
            stroke="var(--consensus-line)"
            stroke-width="1.5"
            stroke-dasharray="3,3"
          />
        </svg>
        <div v-else class="embed-empty-chart">
          <span>{{ $tr('No belief trajectory yet', '暂无信念轨迹', { de: 'Noch keine Überzeugungstrajektorie', fr: `Aucune trajectoire de croyances pour l'instant` }) }}</span>
        </div>

        <div v-if="hasBelief && !chartOnly" class="embed-final-row">
          <span class="final-chip bullish">
            <span class="chip-dot"></span>
            {{ $tr('Bullish', '看涨', { de: 'Optimistisch', fr: 'Haussier' }) }} {{ finalBullish }}%
          </span>
          <span class="final-chip neutral">
            <span class="chip-dot"></span>
            {{ $tr('Neutral', '中立', { de: 'Neutral', fr: 'Neutre' }) }} {{ finalNeutral }}%
          </span>
          <span class="final-chip bearish">
            <span class="chip-dot"></span>
            {{ $tr('Bearish', '看跌', { de: 'Pessimistisch', fr: 'Baissier' }) }} {{ finalBearish }}%
          </span>
        </div>
      </div>

      <footer v-if="!chartOnly" class="embed-footer">
        <div class="embed-footer-left">
          <span v-if="consensusLabel" class="embed-consensus">{{ consensusLabel }}</span>
          <span v-if="resolutionLabel" class="embed-resolution" :class="resolutionClass">
            {{ resolutionLabel }}
          </span>
        </div>
        <a class="embed-footer-link" :href="simulationUrl" target="_blank" rel="noopener">
          {{ $tr('Powered by', '技术支持:', { de: 'Bereitgestellt von', fr: 'Propulsé par' }) }} <strong>MiroShark</strong> ↗
        </a>
      </footer>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getEmbedSummary, getSimulationCost } from '../api/simulation'
import { tr } from '../i18n'

const props = defineProps({
  simulationId: {
    type: String,
    default: ''
  }
})

const route = useRoute()
const simulationId = computed(() => props.simulationId || route.params.simulationId)

const theme = computed(() => (route.query.theme === 'dark' ? 'dark' : 'light'))
const themeClass = computed(() => `theme-${theme.value}`)
const chartOnly = computed(() => route.query.chart_only === 'true' || route.query.chart_only === '1')

const CHART_W = 640
const CHART_H = 180

const loading = ref(true)
const error = ref('')
const summary = ref(null)
const cost = ref(null)

const scenarioTitle = computed(() => {
  const raw = (summary.value?.scenario || '').trim()
  if (!raw) return tr('Untitled simulation', '未命名模拟', { de: 'Unbenannte Simulation', fr: 'Simulation sans titre' })
  return raw.length > 140 ? raw.slice(0, 140).trimEnd() + '…' : raw
})

const simulationUrl = computed(() => {
  if (!simulationId.value) return '/'
  return `${window.location.origin}/simulation/${simulationId.value}/start`
})

const statusLabel = computed(() => {
  if (!summary.value) return tr('Unknown', '未知', { de: 'Unbekannt', fr: 'Inconnu' })
  const s = (summary.value.runner_status || summary.value.status || '').toLowerCase()
  if (s === 'completed' || s === 'finished' || s === 'stopped') return tr('Completed', '已完成', { de: 'Abgeschlossen', fr: 'Terminé' })
  if (s === 'running' || s === 'in_progress') return tr('Running', '运行中', { de: 'Läuft', fr: 'En cours' })
  if (s === 'error' || s === 'failed') return tr('Failed', '失败', { de: 'Fehlgeschlagen', fr: 'Échec' })
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : tr('Ready', '就绪', { de: 'Bereit', fr: 'Prêt' })
})

const statusClass = computed(() => {
  const s = statusLabel.value.toLowerCase()
  return `status-${s}`
})

const isCompleted = computed(() => {
  const s = (summary.value?.runner_status || summary.value?.status || '').toLowerCase()
  return s === 'completed' || s === 'finished' || s === 'stopped'
})

// Human-friendly headline cost from cost.json — the "$1 to simulate
// anything" claim, made visible on every public embed. Empty string when
// there is no cost to show (endpoint 403/404'd, or the run priced to $0),
// which drops the pill entirely. `~` marks the lower-bound estimate;
// sub-cent runs collapse to `<$0.01` rather than a misleading `$0.00`.
const costLabel = computed(() => {
  const usd = cost.value?.estimated_cost_usd
  if (typeof usd !== 'number' || usd <= 0) return ''
  if (usd < 0.01) return '<$0.01'
  const prefix = cost.value?.is_estimate ? '~' : ''
  return `${prefix}$${usd.toFixed(2)}`
})

const hasRounds = computed(() => {
  if (!summary.value) return false
  const total = summary.value.total_rounds || 0
  const current = summary.value.current_round || 0
  return total > 0 || current > 0
})

const hasBelief = computed(() => !!summary.value?.belief?.rounds?.length)

const finalBullish = computed(() => summary.value?.belief?.final?.bullish ?? 0)
const finalNeutral = computed(() => summary.value?.belief?.final?.neutral ?? 0)
const finalBearish = computed(() => summary.value?.belief?.final?.bearish ?? 0)

const qualityClass = computed(() => {
  const h = (summary.value?.quality?.health || '').toLowerCase()
  return `quality-${h || 'unknown'}`
})

const consensusLabel = computed(() => {
  const b = summary.value?.belief
  if (!b?.consensus_round) return ''
  return `${tr('Consensus formed at round', '共识形成于第', { de: 'Konsens erreicht in Runde', fr: 'Consensus atteint au tour' })} ${b.consensus_round} (${b.consensus_stance})`
})

const resolutionLabel = computed(() => {
  const r = summary.value?.resolution
  if (!r) return ''
  if (r.accuracy_score !== null && r.accuracy_score !== undefined) {
    if (r.accuracy_score >= 1.0) return `✓ ${tr('Correct', '正确', { de: 'Richtig', fr: 'Correct' })} · ${tr('Actual', '实际', { de: 'Ergebnis', fr: 'Réel' })} ${r.actual_outcome}`
    if (r.accuracy_score <= 0.0) return `✗ ${tr('Missed', '未中', { de: 'Verfehlt', fr: 'Manqué' })} · ${tr('Actual', '实际', { de: 'Ergebnis', fr: 'Réel' })} ${r.actual_outcome}`
    return `~ ${tr('Split', '部分', { de: 'Geteilt' })} · ${tr('Actual', '实际', { de: 'Ergebnis', fr: 'Réel' })} ${r.actual_outcome}`
  }
  return `${tr('Actual', '实际', { de: 'Ergebnis', fr: 'Réel' })} ${r.actual_outcome}`
})

const resolutionClass = computed(() => {
  const r = summary.value?.resolution
  if (!r || r.accuracy_score === null || r.accuracy_score === undefined) return 'neutral'
  if (r.accuracy_score >= 1.0) return 'correct'
  if (r.accuracy_score <= 0.0) return 'wrong'
  return 'split'
})

const chartAriaLabel = computed(() => {
  if (!hasBelief.value) return tr('No belief trajectory', '无信念轨迹', { de: 'Keine Überzeugungstrajektorie' })
  return `${tr('Belief drift across', '信念漂移历经', { de: 'Überzeugungsdrift über' })} ${summary.value.belief.rounds.length} ${tr('rounds', '轮次', { de: 'Runden', fr: 'tours' })}`
})

// Stacked area chart paths — stack order bullish (top), neutral (middle), bearish (bottom).
// Each row sums to 100, so we paint the three bands as full-width stacked polygons.
const stackPaths = computed(() => {
  if (!hasBelief.value) return { bullish: '', neutral: '', bearish: '' }

  const rounds = summary.value.belief.rounds
  const bu = summary.value.belief.bullish
  const ne = summary.value.belief.neutral
  const be = summary.value.belief.bearish

  const n = rounds.length
  const xStep = n > 1 ? CHART_W / (n - 1) : CHART_W
  const yFor = (pct) => CHART_H - (pct / 100) * CHART_H

  const pts = (topSeries) => {
    const top = topSeries.map((v, i) => `${(i * xStep).toFixed(2)},${yFor(v).toFixed(2)}`).join(' ')
    return top
  }

  // Running top of each stacked band (cumulative percentage from bottom).
  const bullishTop = bu.map(() => 100) // bullish always caps at 100
  const neutralTop = bu.map((_, i) => ne[i] + be[i])
  const bearishTop = be.map((v) => v)

  const bottomLine = Array(n).fill(0)

  const buildBand = (topSeries, bottomSeries) => {
    const top = topSeries.map((v, i) => `${(i * xStep).toFixed(2)},${yFor(v).toFixed(2)}`).join(' L ')
    const bottom = bottomSeries
      .map((v, i) => `${((n - 1 - i) * xStep).toFixed(2)},${yFor(v).toFixed(2)}`)
      .join(' L ')
    return `M ${top} L ${bottom} Z`
  }

  const reversedBottomFor = (arr) => [...arr].reverse()

  return {
    bullish: buildBand(bullishTop, reversedBottomFor(neutralTop)),
    neutral: buildBand(neutralTop, reversedBottomFor(bearishTop)),
    bearish: buildBand(bearishTop, reversedBottomFor(bottomLine))
  }
})

const bullishPath = computed(() => stackPaths.value.bullish)
const neutralPath = computed(() => stackPaths.value.neutral)
const bearishPath = computed(() => stackPaths.value.bearish)

const consensusX = computed(() => {
  const b = summary.value?.belief
  if (!b?.consensus_round || !b.rounds?.length) return null
  const idx = b.rounds.indexOf(b.consensus_round)
  if (idx < 0) return null
  const n = b.rounds.length
  const xStep = n > 1 ? CHART_W / (n - 1) : CHART_W
  return idx * xStep
})

const isCompact = computed(() => {
  // Detect narrow iframe — 480×240 preset
  if (typeof window === 'undefined') return false
  return window.innerWidth < 520
})

const fetchData = async () => {
  if (!simulationId.value) {
    error.value = tr('Missing simulation id', '缺少模拟 ID', { de: 'Simulations-ID fehlt' })
    loading.value = false
    return
  }
  try {
    const res = await getEmbedSummary(simulationId.value)
    if (res?.success) {
      summary.value = res.data
    } else {
      error.value = res?.error || tr('Failed to load simulation', '加载模拟失败', { de: 'Simulation konnte nicht geladen werden' })
    }
  } catch (err) {
    error.value = err?.response?.data?.error || err?.message || tr('Failed to load simulation', '加载模拟失败', { de: 'Simulation konnte nicht geladen werden' })
  } finally {
    loading.value = false
  }

  // Cost is a credibility extra, not a load dependency: fetch it only for
  // finished runs (a live run's cost is partial) and swallow any failure —
  // the publish gate already passed for this embed, but 404/$0 runs simply
  // won't have a figure to show.
  if (summary.value && isCompleted.value) {
    try {
      cost.value = await getSimulationCost(simulationId.value)
    } catch {
      cost.value = null
    }
  }
}

onMounted(() => {
  fetchData()
  // Remove body padding set by main app shell styles (if any) so the embed
  // renders edge-to-edge inside an iframe host.
  if (typeof document !== 'undefined') {
    document.body.style.margin = '0'
    document.body.style.padding = '0'
    document.documentElement.style.background = 'transparent'
    document.body.style.background = 'transparent'
  }
})
</script>

<style scoped>
.embed-widget {
  --bg: #ffffff;
  --fg: #f4f1ff;
  --muted: #6b6b6b;
  --border: rgba(10, 10, 10, 0.08);
  --pill-bg: rgba(10, 10, 10, 0.05);
  --pill-fg: #f4f1ff;
  --bullish: #0ea5a0;
  --neutral: #9aa0a6;
  --bearish: #f07867;
  --consensus-line: rgba(10, 10, 10, 0.45);
  --link-color: #a78bfa;

  box-sizing: border-box;
  width: 100%;
  height: 100vh;
  min-height: 220px;
  padding: 16px 18px;
  background: var(--bg);
  color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 13px;
  line-height: 1.45;
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-radius: 8px;
  overflow: hidden;
}

.embed-widget.theme-dark {
  --bg: #0f1115;
  --fg: #f4f4f5;
  --muted: #a1a1aa;
  --border: rgba(244, 244, 245, 0.12);
  --pill-bg: rgba(244, 244, 245, 0.08);
  --pill-fg: #f4f4f5;
  --consensus-line: rgba(244, 244, 245, 0.55);
}

.embed-widget.chart-only {
  padding: 8px;
  gap: 4px;
}

.embed-widget.compact {
  font-size: 12px;
  padding: 12px 14px;
}

.embed-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 8px;
  color: var(--muted);
}

.embed-error {
  color: var(--bearish);
}

.embed-spinner {
  width: 22px;
  height: 22px;
  border: 2px solid var(--border);
  border-top-color: var(--fg);
  border-radius: 50%;
  animation: embed-spin 0.9s linear infinite;
}

@keyframes embed-spin {
  to { transform: rotate(360deg); }
}

.embed-header {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.embed-scenario {
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.005em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.embed-widget.compact .embed-scenario {
  font-size: 13px;
}

.embed-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.embed-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--pill-bg);
  color: var(--pill-fg);
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}

.embed-pill.status.status-completed {
  background: rgba(14, 165, 160, 0.15);
  color: var(--bullish);
}

.embed-pill.status.status-running {
  background: rgba(234, 88, 12, 0.15);
  color: var(--link-color);
}

.embed-pill.status.status-failed {
  background: rgba(240, 120, 103, 0.15);
  color: var(--bearish);
}

.embed-pill.cost {
  background: rgba(167, 139, 250, 0.15);
  color: var(--link-color);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.embed-pill.quality.quality-excellent {
  background: rgba(14, 165, 160, 0.15);
  color: var(--bullish);
}

.embed-pill.quality.quality-good {
  background: rgba(234, 179, 8, 0.15);
  color: #b45309;
}

.embed-widget.theme-dark .embed-pill.quality.quality-good {
  color: #facc15;
}

.embed-pill.quality.quality-low {
  background: rgba(240, 120, 103, 0.15);
  color: var(--bearish);
}

.embed-chart-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 80px;
}

.embed-chart {
  flex: 1;
  width: 100%;
  height: 100%;
  border-radius: 4px;
  background: var(--pill-bg);
}

.embed-empty-chart {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed var(--border);
  border-radius: 4px;
  color: var(--muted);
  font-size: 11px;
}

.embed-final-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.final-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--pill-bg);
  color: var(--pill-fg);
  font-size: 11px;
  font-weight: 500;
}

.chip-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.final-chip.bullish .chip-dot { background: var(--bullish); }
.final-chip.neutral .chip-dot { background: var(--neutral); }
.final-chip.bearish .chip-dot { background: var(--bearish); }

.embed-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 6px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 11px;
}

.embed-footer-left {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.embed-consensus {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 55ch;
}

.embed-resolution {
  font-weight: 600;
}

.embed-resolution.correct { color: var(--bullish); }
.embed-resolution.wrong { color: var(--bearish); }
.embed-resolution.split { color: var(--muted); }

.embed-footer-link {
  color: var(--link-color);
  text-decoration: none;
  font-weight: 500;
  white-space: nowrap;
}

.embed-footer-link:hover {
  text-decoration: underline;
}

.embed-footer-link strong {
  font-weight: 700;
  letter-spacing: 0.02em;
}
</style>
