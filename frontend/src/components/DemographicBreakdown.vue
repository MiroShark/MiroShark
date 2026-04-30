<template>
  <div class="demographic-breakdown">
    <!-- Header -->
    <div class="demo-header">
      <div class="demo-title">
        <span class="demo-icon">◇</span>
        <span class="demo-label">{{ $tr('DEMOGRAPHIC BREAKDOWN', '人口分布') }}</span>
      </div>
      <div class="demo-header-actions">
        <span v-if="meta" class="demo-meta">
          {{ meta.agents_with_stance }}/{{ meta.total_agents }} {{ $tr('agents with belief data', '个智能体含信念数据') }}
        </span>
        <button
          class="demo-export-btn"
          :disabled="!hasData"
          @click="refresh"
          :title="$tr('Refresh demographic breakdown', '刷新人口分布')"
        >
          ↻ {{ $tr('Refresh', '刷新') }}
        </button>
      </div>
    </div>

    <!-- Tab bar -->
    <div v-if="hasData" class="demo-tabs">
      <button
        v-for="tab in availableTabs"
        :key="tab.key"
        class="demo-tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ translateTabLabel(tab.label) }}
        <span class="demo-tab-count">{{ tabSegmentCount(tab.key) }}</span>
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="demo-state">
      <div class="pulse-ring"></div>
      <span>{{ $tr('Computing demographic breakdown...', '正在计算人口分布...') }}</span>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="demo-state demo-error-state">{{ error }}</div>

    <!-- No data -->
    <div v-else-if="!hasData" class="demo-state">
      <span>{{ $tr('No demographic data available.', '暂无人口数据。') }}</span>
      <span class="demo-hint">{{ $tr('Run a simulation to generate agent profiles.', '运行一次模拟以生成智能体画像。') }}</span>
    </div>

    <!-- Main content -->
    <div v-else class="demo-content">
      <!-- Top divergence callout -->
      <div v-if="topDivergence" class="demo-highlight">
        <span class="demo-highlight-label">{{ $tr('KEY SUBGROUP DYNAMIC', '关键子群体动态') }}</span>
        <span class="demo-highlight-text">{{ topDivergence.headline }}</span>
      </div>
      <div v-else-if="meta && !meta.has_trajectory" class="demo-highlight demo-highlight-muted">
        <span class="demo-highlight-label">{{ $tr('NOTICE', '提示') }}</span>
        <span class="demo-highlight-text">
          {{ $tr('This simulation has no belief trajectory — stance comparisons will be unavailable, but counts and influence remain accurate.', '此模拟没有信念轨迹 — 立场对比将不可用,但数量和影响力数据仍然准确。') }}
        </span>
      </div>

      <!-- Legend -->
      <div class="demo-legend">
        <span class="legend-item"><span class="legend-dot bullish-dot"></span>{{ $tr('Bullish', '看涨') }}</span>
        <span class="legend-item"><span class="legend-dot neutral-dot"></span>{{ $tr('Neutral', '中立') }}</span>
        <span class="legend-item"><span class="legend-dot bearish-dot"></span>{{ $tr('Bearish', '看跌') }}</span>
        <span class="legend-sep">·</span>
        <span class="legend-item">{{ $tr('Stance mean: -1 ↔ +1', '立场均值: -1 ↔ +1') }}</span>
      </div>

      <!-- Segment list for active tab -->
      <div class="demo-segments">
        <div
          v-for="segment in activeSegments"
          :key="segment.label"
          class="demo-row"
        >
          <div class="demo-row-head">
            <span class="demo-row-label">{{ formatSegmentLabel(segment.label) }}</span>
            <span class="demo-row-count">{{ segment.count }} {{ $tr(segment.count === 1 ? 'agent' : 'agents', '个智能体') }}</span>
          </div>

          <!-- Stance distribution bar -->
          <div class="stance-bar" v-if="hasStanceData(segment)">
            <div
              class="stance-seg stance-bullish"
              :style="{ width: segment.bullish_pct + '%' }"
              :title="$tr('Bullish:', '看涨:') + ` ${segment.bullish_pct}%`"
            ></div>
            <div
              class="stance-seg stance-neutral"
              :style="{ width: segment.neutral_pct + '%' }"
              :title="$tr('Neutral:', '中立:') + ` ${segment.neutral_pct}%`"
            ></div>
            <div
              class="stance-seg stance-bearish"
              :style="{ width: segment.bearish_pct + '%' }"
              :title="$tr('Bearish:', '看跌:') + ` ${segment.bearish_pct}%`"
            ></div>
          </div>
          <div v-else class="stance-bar stance-empty"></div>

          <!-- Metrics row -->
          <div class="demo-metrics">
            <span class="metric">
              <span class="metric-label">{{ $tr('mean', '均值') }}</span>
              <span class="metric-value" :class="stanceClass(segment.final_stance_mean)">
                {{ formatStance(segment.final_stance_mean) }}
              </span>
            </span>
            <span class="metric">
              <span class="metric-label">σ</span>
              <span class="metric-value">{{ formatNumber(segment.final_stance_std) }}</span>
            </span>
            <span class="metric">
              <span class="metric-label">{{ $tr('volatility', '波动率') }}</span>
              <span class="metric-value">{{ formatNumber(segment.stance_volatility) }}</span>
            </span>
            <span class="metric">
              <span class="metric-label">{{ $tr('influence', '影响力') }}</span>
              <span class="metric-value">{{ formatInfluence(segment.influence_mean) }}</span>
            </span>
          </div>
        </div>
      </div>

      <!-- Footer hint -->
      <div class="demo-footer-hint">
        {{ $tr(`Stance values average each agent's final belief across tracked topics (-1 bearish → +1 bullish). Volatility is the mean absolute change from round 0 to the final round.`, '立场值为每个智能体在跟踪话题上的最终信念均值(-1 看跌 → +1 看涨)。波动率为从第 0 轮到最终轮的绝对变化均值。') }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getDemographicBreakdown } from '../api/simulation'
import { tr } from '../i18n'

const props = defineProps({
  simulationId: { type: String, required: true },
  visible: { type: Boolean, default: false },
})

const loading = ref(false)
const error = ref('')
const payload = ref(null)
const activeTab = ref('by_age_range')

const TABS = [
  { key: 'by_age_range', label: 'Age' },
  { key: 'by_gender', label: 'Gender' },
  { key: 'by_country', label: 'Country' },
  { key: 'by_archetype', label: 'Actor type' },
  { key: 'by_platform', label: 'Platform' },
]

const hasData = computed(() => !!payload.value?.dimensions)
const meta = computed(() => payload.value?.meta || null)
const topDivergence = computed(() => payload.value?.top_divergence || null)

const availableTabs = computed(() => {
  if (!hasData.value) return []
  return TABS.filter(t => {
    const dim = payload.value.dimensions[t.key]
    return dim && Object.keys(dim).length > 0
  })
})

const tabSegmentCount = (key) => {
  if (!hasData.value) return 0
  const dim = payload.value.dimensions[key]
  return dim ? Object.keys(dim).length : 0
}

const activeSegments = computed(() => {
  if (!hasData.value) return []
  const dim = payload.value.dimensions[activeTab.value] || {}
  return Object.entries(dim).map(([label, data]) => ({ label, ...data }))
})

const hasStanceData = (segment) =>
  (segment.bullish_pct + segment.neutral_pct + segment.bearish_pct) > 0

const formatSegmentLabel = (raw) => {
  if (!raw) return tr('unknown', '未知')
  const map = {
    unknown: tr('Unknown', '未知'),
    individual: tr('Individual', '个人'),
    institutional: tr('Institutional', '机构'),
    inactive: tr('Inactive', '不活跃'),
    male: tr('Male', '男性'),
    female: tr('Female', '女性'),
    other: tr('Other', '其他'),
    twitter: 'X / Twitter',
    reddit: 'Reddit',
    polymarket: 'Polymarket',
  }
  return map[raw] || raw
}

const translateTabLabel = (label) => {
  const map = {
    'Age': tr('Age', '年龄'),
    'Gender': tr('Gender', '性别'),
    'Country': tr('Country', '国家'),
    'Actor type': tr('Actor type', '主体类型'),
    'Platform': tr('Platform', '平台'),
  }
  return map[label] || label
}

const formatStance = (v) => {
  if (v === null || v === undefined) return '—'
  const sign = v > 0 ? '+' : ''
  return sign + v.toFixed(2)
}

const formatNumber = (v) => {
  if (v === null || v === undefined) return '—'
  return v.toFixed(2)
}

const formatInfluence = (v) => {
  if (v === null || v === undefined) return '—'
  return v.toFixed(0)
}

const stanceClass = (v) => {
  if (v === null || v === undefined) return ''
  if (v > 0.1) return 'stance-val-bullish'
  if (v < -0.1) return 'stance-val-bearish'
  return 'stance-val-neutral'
}

const load = async (opts = {}) => {
  if (!props.simulationId) return
  loading.value = true
  error.value = ''
  try {
    const res = await getDemographicBreakdown(props.simulationId, opts)
    if (res.success && res.data) {
      payload.value = res.data
      const first = availableTabs.value[0]
      if (first && !availableTabs.value.find(t => t.key === activeTab.value)) {
        activeTab.value = first.key
      }
    } else if (res.success && !res.data) {
      payload.value = null
    } else {
      error.value = res.error || tr('Failed to load demographic breakdown.', '加载人口分布失败。')
    }
  } catch (err) {
    error.value = err.message || tr('Failed to load demographic breakdown.', '加载人口分布失败。')
  } finally {
    loading.value = false
  }
}

const refresh = () => load({ refresh: true })

watch(() => props.visible, (val) => { if (val) load() })
watch(() => props.simulationId, () => { if (props.visible) load() })
onMounted(() => { if (props.visible) load() })
</script>

<style scoped>
.demographic-breakdown {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  font-family: var(--font-mono);
  background: var(--background);
}

.demo-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.08);
  flex-shrink: 0;
}

.demo-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.demo-icon {
  color: #ec4899;
  font-size: 14px;
}

.demo-label {
  font-size: 12px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.5);
}

.demo-header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.demo-meta {
  font-size: 10px;
  letter-spacing: 1px;
  color: rgba(10,10,10,0.4);
}

.demo-export-btn {
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

.demo-export-btn:hover:not(:disabled) {
  border-color: #ec4899;
  color: #ec4899;
}

.demo-export-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.demo-tabs {
  display: flex;
  gap: 0;
  padding: 0 12px;
  border-bottom: 1px solid rgba(10,10,10,0.05);
  flex-shrink: 0;
  overflow-x: auto;
}

.demo-tab {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  padding: 10px 14px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.4);
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.demo-tab:hover {
  color: rgba(10,10,10,0.7);
}

.demo-tab.active {
  color: #ec4899;
  border-bottom-color: #ec4899;
}

.demo-tab-count {
  font-size: 9px;
  opacity: 0.5;
  background: rgba(10,10,10,0.06);
  padding: 1px 5px;
  border-radius: 8px;
  letter-spacing: 0;
}

.demo-tab.active .demo-tab-count {
  background: rgba(236,72,153,0.15);
  color: #ec4899;
  opacity: 1;
}

.demo-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 8px;
  color: rgba(10,10,10,0.4);
  font-size: 12px;
  letter-spacing: 1px;
}

.demo-error-state {
  color: rgba(239,68,68,0.8);
}

.demo-hint {
  font-size: 10px;
  color: rgba(10,10,10,0.3);
}

.pulse-ring {
  width: 24px;
  height: 24px;
  border: 2px solid rgba(236,72,153,0.15);
  border-top-color: rgba(236,72,153,0.7);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.demo-content {
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  flex: 1;
  padding: 12px 16px 16px;
  gap: 14px;
}

.demo-highlight {
  background: rgba(236,72,153,0.06);
  border-left: 3px solid #ec4899;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.demo-highlight-muted {
  background: rgba(10,10,10,0.04);
  border-left-color: rgba(10,10,10,0.2);
}

.demo-highlight-label {
  font-size: 9px;
  letter-spacing: 2px;
  color: #ec4899;
  text-transform: uppercase;
}

.demo-highlight-muted .demo-highlight-label {
  color: rgba(10,10,10,0.4);
}

.demo-highlight-text {
  font-size: 12px;
  color: rgba(10,10,10,0.8);
  line-height: 1.5;
}

.demo-legend {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  font-size: 10px;
  color: rgba(10,10,10,0.4);
  letter-spacing: 1px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.bullish-dot { background: rgba(20,184,166,0.8); }
.neutral-dot { background: rgba(148,163,184,0.8); }
.bearish-dot { background: rgba(239,68,68,0.8); }

.legend-sep {
  color: rgba(10,10,10,0.15);
}

.demo-segments {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.demo-row {
  padding: 10px 12px;
  background: rgba(10,10,10,0.02);
  border: 1px solid rgba(10,10,10,0.04);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.demo-row-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.demo-row-label {
  font-size: 12px;
  color: rgba(10,10,10,0.8);
  letter-spacing: 0.5px;
}

.demo-row-count {
  font-size: 10px;
  color: rgba(10,10,10,0.4);
  letter-spacing: 1px;
}

.stance-bar {
  display: flex;
  height: 8px;
  background: rgba(10,10,10,0.04);
  border-radius: 2px;
  overflow: hidden;
}

.stance-bar.stance-empty {
  opacity: 0.4;
}

.stance-seg {
  height: 100%;
  transition: width 0.25s ease;
}

.stance-bullish { background: rgba(20,184,166,0.75); }
.stance-neutral { background: rgba(148,163,184,0.55); }
.stance-bearish { background: rgba(239,68,68,0.75); }

.demo-metrics {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  padding-top: 2px;
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 56px;
}

.metric-label {
  font-size: 9px;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.35);
}

.metric-value {
  font-size: 13px;
  color: rgba(10,10,10,0.85);
  letter-spacing: 0.5px;
}

.stance-val-bullish { color: rgba(13,148,136,0.95); }
.stance-val-bearish { color: rgba(220,38,38,0.95); }
.stance-val-neutral { color: rgba(100,116,139,0.9); }

.demo-footer-hint {
  font-size: 10px;
  color: rgba(10,10,10,0.35);
  line-height: 1.6;
  border-top: 1px solid rgba(10,10,10,0.05);
  padding-top: 10px;
  margin-top: 4px;
}
</style>
