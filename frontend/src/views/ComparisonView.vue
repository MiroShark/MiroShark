<template>
  <div class="comparison-page">
    <!-- Header -->
    <header class="cmp-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">MIROSHARK</div>
      </div>
      <div class="header-center">
        <span class="page-tag">{{ $tr('Simulation Comparison', '模拟对比') }}</span>
      </div>
      <div class="header-right">
        <button v-if="data" class="download-btn" @click="downloadComparison">
          {{ $tr('↓ Export JSON', '↓ 导出 JSON') }}
        </button>
        <LocaleToggle />
      </div>
    </header>

    <!-- Simulation Selector -->
    <div class="selector-bar">
      <div class="selector-group">
        <label class="selector-label">{{ $tr('Simulation A', '模拟 A') }}</label>
        <select class="sim-select" v-model="selectedId1" @change="onSelectionChange">
          <option value="">{{ $tr('Select simulation…', '选择模拟…') }}</option>
          <option v-for="s in simulations" :key="s.simulation_id" :value="s.simulation_id">
            {{ formatId(s.simulation_id) }} — {{ s.status }}
          </option>
        </select>
      </div>

      <div class="vs-badge">{{ $tr('VS', '对比') }}</div>

      <div class="selector-group">
        <label class="selector-label">{{ $tr('Simulation B', '模拟 B') }}</label>
        <select class="sim-select" v-model="selectedId2" @change="onSelectionChange">
          <option value="">{{ $tr('Select simulation…', '选择模拟…') }}</option>
          <option v-for="s in simulations" :key="s.simulation_id" :value="s.simulation_id">
            {{ formatId(s.simulation_id) }} — {{ s.status }}
          </option>
        </select>
      </div>

      <button
        class="compare-btn"
        :disabled="!selectedId1 || !selectedId2 || selectedId1 === selectedId2 || loading"
        @click="runComparison"
      >
        <span v-if="loading" class="loading-spinner-small"></span>
        {{ loading ? $tr('Comparing…', '对比中…') : $tr('Compare', '对比') }}
      </button>
    </div>

    <!-- Error -->
    <div v-if="error" class="cmp-error">{{ error }}</div>

    <!-- Loading -->
    <div v-else-if="loading" class="cmp-loading">
      <div class="loading-ring"></div>
      <span>{{ $tr('Running comparison…', '正在对比…') }}</span>
    </div>

    <!-- Results -->
    <div v-else-if="data" class="cmp-results">

      <!-- Divergence Banner -->
      <div class="divergence-banner">
        <div class="divergence-label">{{ $tr('Outcome Divergence Score', '结果分歧度') }}</div>
        <div class="divergence-score" :class="divergenceClass">
          {{ (data.divergence_score * 100).toFixed(1) }}%
        </div>
        <div class="divergence-desc">{{ divergenceDescription }}</div>
      </div>

      <!-- Key Metrics Row -->
      <div class="metrics-row">
        <div class="metric-card sim-a">
          <div class="metric-sim-id">{{ formatId(data.id1) }}</div>
          <div class="metric-grid">
            <div class="metric-item">
              <span class="metric-val">{{ data.sim1.profiles_count }}</span>
              <span class="metric-lbl">{{ $tr('Agents', '智能体') }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-val">{{ data.sim1.total_rounds }}</span>
              <span class="metric-lbl">{{ $tr('Rounds', '轮次') }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-val">{{ data.sim1.total_actions.toLocaleString() }}</span>
              <span class="metric-lbl">{{ $tr('Actions', '动作') }}</span>
            </div>
          </div>
        </div>

        <div class="metric-card sim-b">
          <div class="metric-sim-id">{{ formatId(data.id2) }}</div>
          <div class="metric-grid">
            <div class="metric-item">
              <span class="metric-val">{{ data.sim2.profiles_count }}</span>
              <span class="metric-lbl">{{ $tr('Agents', '智能体') }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-val">{{ data.sim2.total_rounds }}</span>
              <span class="metric-lbl">{{ $tr('Rounds', '轮次') }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-val">{{ data.sim2.total_actions.toLocaleString() }}</span>
              <span class="metric-lbl">{{ $tr('Actions', '动作') }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Two-Column Layout -->
      <div class="two-col-layout">

        <!-- Influence Leaderboard Comparison -->
        <div class="cmp-section full-width">
          <div class="section-title">{{ $tr('Influence Leaderboard', '影响力榜单') }}</div>
          <div class="leaderboard-compare">
            <div class="lb-col">
              <div class="lb-header sim-a-color">{{ formatId(data.id1) }}</div>
              <div
                v-for="agent in data.sim1.influence"
                :key="agent.agent_name"
                class="lb-row"
              >
                <span class="lb-rank">#{{ agent.rank }}</span>
                <span class="lb-name">{{ agent.agent_name }}</span>
                <span class="lb-score">{{ agent.influence_score }}</span>
                <span
                  class="lb-delta"
                  :class="getRankDeltaClass(agent.agent_name, 'sim1')"
                  :title="getRankDeltaTitle(agent.agent_name, 'sim1')"
                >{{ getRankDeltaLabel(agent.agent_name, 'sim1') }}</span>
              </div>
              <div v-if="!data.sim1.influence.length" class="lb-empty">{{ $tr('No data', '无数据') }}</div>
            </div>

            <div class="lb-col">
              <div class="lb-header sim-b-color">{{ formatId(data.id2) }}</div>
              <div
                v-for="agent in data.sim2.influence"
                :key="agent.agent_name"
                class="lb-row"
              >
                <span class="lb-rank">#{{ agent.rank }}</span>
                <span class="lb-name">{{ agent.agent_name }}</span>
                <span class="lb-score">{{ agent.influence_score }}</span>
                <span
                  class="lb-delta"
                  :class="getRankDeltaClass(agent.agent_name, 'sim2')"
                  :title="getRankDeltaTitle(agent.agent_name, 'sim2')"
                >{{ getRankDeltaLabel(agent.agent_name, 'sim2') }}</span>
              </div>
              <div v-if="!data.sim2.influence.length" class="lb-empty">{{ $tr('No data', '无数据') }}</div>
            </div>
          </div>
        </div>

        <!-- Activity Timeline Chart -->
        <div class="cmp-section full-width" v-if="data.sim1.timeline.length || data.sim2.timeline.length">
          <div class="section-title">{{ $tr('Activity per Round', '每轮活动量') }}</div>
          <div class="chart-container">
            <svg ref="chartSvg" class="activity-chart" :viewBox="`0 0 ${chartW} ${chartH}`" preserveAspectRatio="none">
              <!-- Grid lines -->
              <line
                v-for="i in 5"
                :key="'h'+i"
                :x1="chartPad"
                :x2="chartW - chartPad"
                :y1="chartPad + ((chartH - 2*chartPad) / 4) * (i-1)"
                :y2="chartPad + ((chartH - 2*chartPad) / 4) * (i-1)"
                stroke="#1E1E1E"
                stroke-width="1"
              />
              <!-- Sim A line -->
              <polyline
                v-if="chartPoints1.length > 1"
                :points="chartPoints1.map(p => `${p.x},${p.y}`).join(' ')"
                fill="none"
                stroke="#FF6B1A"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <!-- Sim B line -->
              <polyline
                v-if="chartPoints2.length > 1"
                :points="chartPoints2.map(p => `${p.x},${p.y}`).join(' ')"
                fill="none"
                stroke="#43C165"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <!-- Dots Sim A -->
              <circle
                v-for="p in chartPoints1"
                :key="'a'+p.round"
                :cx="p.x" :cy="p.y" r="3"
                fill="#FF6B1A"
              />
              <!-- Dots Sim B -->
              <circle
                v-for="p in chartPoints2"
                :key="'b'+p.round"
                :cx="p.x" :cy="p.y" r="3"
                fill="#43C165"
              />
            </svg>
            <div class="chart-legend">
              <span class="legend-item sim-a-color">● {{ formatId(data.id1) }}</span>
              <span class="legend-item sim-b-color">● {{ formatId(data.id2) }}</span>
              <span class="legend-label">{{ $tr('Total actions / round', '每轮动作总数') }}</span>
            </div>
          </div>
        </div>

        <!-- Market Prices (if available) -->
        <div
          class="cmp-section full-width"
          v-if="data.sim1.markets.length || data.sim2.markets.length"
        >
          <div class="section-title">{{ $tr('Prediction Market Final Prices', '预测市场最终价格') }}</div>
          <div class="markets-compare">
            <div class="market-col">
              <div class="market-col-header sim-a-color">{{ formatId(data.id1) }}</div>
              <div v-for="m in data.sim1.markets" :key="m.market_id" class="market-row">
                <span class="market-id">{{ $tr('Market', '市场') }} {{ m.market_id }}</span>
                <div class="market-bar-wrap">
                  <div class="market-bar" :style="{ width: (m.price_yes * 100) + '%', background: '#FF6B1A' }"></div>
                </div>
                <span class="market-price">{{ (m.price_yes * 100).toFixed(1) }}% {{ $tr('YES', '是') }}</span>
              </div>
            </div>
            <div class="market-col">
              <div class="market-col-header sim-b-color">{{ formatId(data.id2) }}</div>
              <div v-for="m in data.sim2.markets" :key="m.market_id" class="market-row">
                <span class="market-id">{{ $tr('Market', '市场') }} {{ m.market_id }}</span>
                <div class="market-bar-wrap">
                  <div class="market-bar" :style="{ width: (m.price_yes * 100) + '%', background: '#43C165' }"></div>
                </div>
                <span class="market-price">{{ (m.price_yes * 100).toFixed(1) }}% {{ $tr('YES', '是') }}</span>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="!loading && !error" class="cmp-empty">
      <p>{{ $tr('Select two simulations above and click Compare to see the diff.', '在上方选择两个模拟并点击对比以查看差异。') }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { compareSimulations, listSimulations } from '../api/simulation'
import LocaleToggle from '../components/LocaleToggle.vue'
import { tr } from '../i18n'

const router = useRouter()
const route = useRoute()

const simulations = ref([])
const selectedId1 = ref(route.params.id1 || '')
const selectedId2 = ref(route.params.id2 || '')
const data = ref(null)
const loading = ref(false)
const error = ref(null)

// Chart dimensions
const chartW = 600
const chartH = 200
const chartPad = 20

onMounted(async () => {
  try {
    const res = await listSimulations()
    if (res.data?.success) {
      simulations.value = res.data.data?.simulations || []
    }
  } catch (_) {}

  // Auto-run if IDs provided via URL
  if (selectedId1.value && selectedId2.value) {
    await runComparison()
  }
})

watch(() => route.params, async (params) => {
  if (params.id1 && params.id2) {
    selectedId1.value = params.id1
    selectedId2.value = params.id2
    await runComparison()
  }
})

const onSelectionChange = () => {
  // Update URL without triggering navigation
  if (selectedId1.value && selectedId2.value && selectedId1.value !== selectedId2.value) {
    router.replace({ name: 'Compare', params: { id1: selectedId1.value, id2: selectedId2.value } })
  }
}

const runComparison = async () => {
  if (!selectedId1.value || !selectedId2.value) return
  loading.value = true
  error.value = null
  data.value = null
  try {
    const res = await compareSimulations(selectedId1.value, selectedId2.value)
    if (res.data?.success) {
      data.value = res.data.data
    } else {
      error.value = res.data?.error || tr('Comparison failed', '对比失败')
    }
  } catch (err) {
    error.value = err?.response?.data?.error || err.message || tr('Comparison failed', '对比失败')
  } finally {
    loading.value = false
  }
}

const formatId = (id) => {
  if (!id) return '—'
  return id.replace(/^sim_/, '').slice(0, 10) + '…'
}

const divergenceClass = computed(() => {
  if (!data.value) return ''
  const s = data.value.divergence_score
  if (s < 0.2) return 'low'
  if (s < 0.5) return 'medium'
  return 'high'
})

const divergenceDescription = computed(() => {
  if (!data.value) return ''
  const s = data.value.divergence_score
  if (s < 0.2) return tr('Simulations produced very similar influence rankings — comparable outcomes.', '两次模拟的影响力排名非常相似 — 结果可比。')
  if (s < 0.5) return tr('Moderate divergence — some agents shifted in relative influence between runs.', '中等分歧 — 部分智能体在两次运行中相对影响力发生变化。')
  return tr('High divergence — the two simulations produced substantially different influence outcomes.', '高度分歧 — 两次模拟产生了截然不同的影响力结果。')
})

// Rank delta helpers
const getRankDeltaLabel = (name, simKey) => {
  const other = simKey === 'sim1' ? data.value?.sim2 : data.value?.sim1
  if (!other) return ''
  const myRank = (simKey === 'sim1' ? data.value.sim1 : data.value.sim2)
    .influence.find(a => a.agent_name === name)?.rank
  const otherRank = other.influence.find(a => a.agent_name === name)?.rank
  if (!otherRank) return '—'
  const delta = otherRank - myRank
  if (delta === 0) return '='
  return delta > 0 ? `▲${delta}` : `▼${Math.abs(delta)}`
}

const getRankDeltaClass = (name, simKey) => {
  const label = getRankDeltaLabel(name, simKey)
  if (label.startsWith('▲')) return 'delta-up'
  if (label.startsWith('▼')) return 'delta-down'
  return 'delta-equal'
}

const getRankDeltaTitle = (name, simKey) => {
  const label = getRankDeltaLabel(name, simKey)
  if (label === '—') return tr('Not in other simulation\'s top 10', '不在另一次模拟的前 10 名中')
  if (label === '=') return tr('Same rank in both simulations', '两次模拟中排名相同')
  return `${tr('Rank difference:', '排名差:')} ${label.replace(/[▲▼]/, '')}`
}

// Chart point computation — shared Y-axis scale across both timelines
const sharedChartMax = computed(() => {
  const t1 = data.value?.sim1?.timeline || []
  const t2 = data.value?.sim2?.timeline || []
  const all = [...t1, ...t2].map(r => r.total_actions)
  return Math.max(...all, 1)
})

const sharedRoundRange = computed(() => {
  const t1 = data.value?.sim1?.timeline || []
  const t2 = data.value?.sim2?.timeline || []
  const allRounds = [...t1, ...t2].map(r => r.round_num)
  if (!allRounds.length) return { min: 0, range: 1 }
  const min = Math.min(...allRounds)
  const max = Math.max(...allRounds)
  return { min, range: Math.max(max - min, 1) }
})

const buildChartPoints = (timeline) => {
  if (!timeline || !timeline.length) return []
  const maxActions = sharedChartMax.value
  const { min: minR, range: rangeR } = sharedRoundRange.value
  return timeline.map(r => ({
    round: r.round_num,
    x: chartPad + ((r.round_num - minR) / rangeR) * (chartW - 2 * chartPad),
    y: chartH - chartPad - (r.total_actions / maxActions) * (chartH - 2 * chartPad),
  }))
}

const chartPoints1 = computed(() => buildChartPoints(data.value?.sim1?.timeline))
const chartPoints2 = computed(() => buildChartPoints(data.value?.sim2?.timeline))

// Download comparison JSON
const downloadComparison = () => {
  if (!data.value) return
  const blob = new Blob([JSON.stringify(data.value, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `comparison_${selectedId1.value.slice(-6)}_${selectedId2.value.slice(-6)}.json`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.comparison-page {
  min-height: 100vh;
  background: #0A0A0A;
  color: #FAFAFA;
  font-family: 'Space Mono', monospace;
}

.cmp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 32px;
  border-bottom: 1px solid #1E1E1E;
}
.brand {
  font-family: 'Young Serif', serif;
  font-size: 18px;
  color: #FF6B1A;
  cursor: pointer;
}
.page-tag {
  font-size: 12px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}
.download-btn {
  padding: 7px 16px;
  border: 1px solid #3A3A3A;
  background: transparent;
  color: #ccc;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  font-family: inherit;
  transition: all 0.15s;
}
.download-btn:hover {
  border-color: #FF6B1A;
  color: #FF6B1A;
}

/* Selector Bar */
.selector-bar {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  padding: 20px 32px;
  border-bottom: 1px solid #1A1A1A;
  background: #0D0D0D;
}
.selector-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}
.selector-label {
  font-size: 11px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.sim-select {
  padding: 8px 12px;
  background: #151515;
  border: 1px solid #2A2A2A;
  color: #ccc;
  border-radius: 4px;
  font-family: 'Space Mono', monospace;
  font-size: 12px;
  cursor: pointer;
  width: 100%;
}
.sim-select:focus {
  outline: none;
  border-color: #FF6B1A;
}
.vs-badge {
  padding: 8px 14px;
  border: 1px solid #3A3A3A;
  border-radius: 4px;
  color: #555;
  font-size: 11px;
  font-weight: bold;
  letter-spacing: 0.1em;
  flex-shrink: 0;
}
.compare-btn {
  padding: 9px 24px;
  background: #FF6B1A;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  font-family: inherit;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  transition: opacity 0.15s;
}
.compare-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* Error / Loading / Empty */
.cmp-error {
  margin: 32px;
  padding: 14px;
  background: rgba(255, 68, 68, 0.1);
  border: 1px solid #FF4444;
  border-radius: 6px;
  color: #FF4444;
  font-size: 13px;
}
.cmp-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 60px;
  color: #555;
  font-size: 13px;
}
.loading-ring {
  width: 36px;
  height: 36px;
  border: 3px solid #2A2A2A;
  border-top-color: #FF6B1A;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.cmp-empty {
  padding: 60px 32px;
  text-align: center;
  color: #444;
  font-size: 13px;
}

/* Results */
.cmp-results {
  padding: 24px 32px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* Divergence Banner */
.divergence-banner {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 16px 24px;
  background: #111;
  border: 1px solid #2A2A2A;
  border-radius: 8px;
}
.divergence-label { font-size: 11px; color: #555; text-transform: uppercase; letter-spacing: 0.08em; }
.divergence-score {
  font-size: 28px;
  font-weight: bold;
}
.divergence-score.low { color: #43C165; }
.divergence-score.medium { color: #FFB347; }
.divergence-score.high { color: #FF6B1A; }
.divergence-desc { font-size: 12px; color: #888; max-width: 400px; line-height: 1.5; }

/* Metrics Row */
.metrics-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.metric-card {
  padding: 16px 20px;
  background: #111;
  border: 1px solid #2A2A2A;
  border-radius: 8px;
}
.metric-card.sim-a { border-top: 3px solid #FF6B1A; }
.metric-card.sim-b { border-top: 3px solid #43C165; }
.metric-sim-id { font-size: 11px; color: #555; margin-bottom: 12px; font-family: 'Space Mono', monospace; }
.metric-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.metric-item { display: flex; flex-direction: column; gap: 4px; }
.metric-val { font-size: 20px; color: #FAFAFA; font-weight: bold; }
.metric-lbl { font-size: 10px; color: #555; text-transform: uppercase; letter-spacing: 0.08em; }

/* Two-column layout */
.two-col-layout { display: flex; flex-direction: column; gap: 20px; }

/* Section */
.cmp-section { background: #111; border: 1px solid #2A2A2A; border-radius: 8px; padding: 20px; }
.cmp-section.full-width { width: 100%; }
.section-title { font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: #666; margin-bottom: 16px; }

/* Leaderboard */
.leaderboard-compare { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.lb-col {}
.lb-header {
  font-size: 11px;
  font-family: 'Space Mono', monospace;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #2A2A2A;
}
.lb-row {
  display: grid;
  grid-template-columns: 28px 1fr 50px 36px;
  align-items: center;
  gap: 6px;
  padding: 6px 0;
  border-bottom: 1px solid #161616;
  font-size: 12px;
}
.lb-rank { color: #555; font-size: 11px; }
.lb-name { color: #ccc; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lb-score { color: #888; text-align: right; font-size: 11px; }
.lb-delta { font-size: 10px; text-align: center; font-weight: bold; }
.delta-up { color: #43C165; }
.delta-down { color: #FF6B1A; }
.delta-equal { color: #555; }
.lb-empty { color: #444; font-size: 12px; padding: 12px 0; }

/* Chart */
.chart-container { display: flex; flex-direction: column; gap: 12px; }
.activity-chart {
  width: 100%;
  height: 180px;
  background: #0D0D0D;
  border-radius: 4px;
  border: 1px solid #1E1E1E;
}
.chart-legend { display: flex; gap: 20px; font-size: 11px; color: #666; }
.legend-item { }
.legend-label { color: #444; margin-left: auto; }
.sim-a-color { color: #FF6B1A; }
.sim-b-color { color: #43C165; }

/* Markets */
.markets-compare { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.market-col { }
.market-col-header { font-size: 11px; font-family: 'Space Mono', monospace; margin-bottom: 8px; }
.market-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 11px; }
.market-id { color: #555; width: 60px; flex-shrink: 0; }
.market-bar-wrap { flex: 1; height: 8px; background: #1A1A1A; border-radius: 4px; overflow: hidden; }
.market-bar { height: 100%; border-radius: 4px; transition: width 0.3s; }
.market-price { width: 70px; text-align: right; color: #ccc; }

/* Loading spinner */
.loading-spinner-small {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
</style>
