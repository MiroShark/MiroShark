<template>
  <div class="comparison-page">
    <!-- Header -->
    <header class="cmp-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">
          <img src="/shark.webp" alt="" class="brand-mark" />
          <span>MiroShark</span>
        </div>
      </div>
      <div class="header-center">
        <span class="page-tag">{{ $tr('Simulation Comparison', '模拟对比', { de: 'Simulationsvergleich', fr: 'Comparaison des simulations' }) }}</span>
      </div>
      <div class="header-right">
        <button v-if="data" class="download-btn" @click="downloadComparison">
          {{ $tr('↓ Export JSON', '↓ 导出 JSON', { de: '↓ JSON exportieren', fr: 'Comparaison de simulations' }) }}
        </button>
        <LocaleToggle />
      </div>
    </header>

    <!-- Simulation Selector -->
    <div class="selector-bar">
      <div class="selector-group">
        <label class="selector-label">{{ $tr('Simulation A', '模拟 A', { de: 'Simulation A', fr: 'Simulation A' }) }}</label>
        <select class="sim-select" v-model="selectedId1" @change="onSelectionChange">
          <option value="">{{ $tr('Select simulation…', '选择模拟…', { de: 'Simulation auswählen…', fr: 'Sélectionner une simulation…' }) }}</option>
          <option v-for="s in simulations" :key="s.simulation_id" :value="s.simulation_id">
            {{ formatId(s.simulation_id) }} — {{ s.status }}
          </option>
        </select>
      </div>

      <div class="vs-badge">{{ $tr('VS', '对比', { de: 'VS', fr: 'VS' }) }}</div>

      <div class="selector-group">
        <label class="selector-label">{{ $tr('Simulation B', '模拟 B', { de: 'Simulation B', fr: 'Simulation B' }) }}</label>
        <select class="sim-select" v-model="selectedId2" @change="onSelectionChange">
          <option value="">{{ $tr('Select simulation…', '选择模拟…', { de: 'Simulation auswählen…', fr: 'Sélectionner une simulation…' }) }}</option>
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
        {{ loading ? $tr('Comparing…', '对比中…', { de: 'Vergleich läuft…', fr: 'Comparaison…' }) : $tr('Compare', '对比', { de: 'Vergleichen', fr: 'Comparer' }) }}
      </button>
    </div>

    <!-- Error -->
    <div v-if="error" class="cmp-error">{{ error }}</div>

    <!-- Loading -->
    <div v-else-if="loading" class="cmp-loading">
      <div class="loading-ring"></div>
      <span>{{ $tr('Running comparison…', '正在对比…', { de: 'Vergleich wird durchgeführt…', fr: 'Comparaison en cours…' }) }}</span>
    </div>

    <!-- Results -->
    <div v-else-if="data" class="cmp-results">

      <!-- Divergence Banner -->
      <div class="divergence-banner">
        <div class="divergence-label">{{ $tr('Outcome Divergence Score', '结果分歧度', { de: 'Ergebnis-Divergenzwert', fr: 'Score de divergence des résultats' }) }}</div>
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
              <span class="metric-lbl">{{ $tr('Agents', '智能体', { de: 'Agenten', fr: 'Agents' }) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-val">{{ data.sim1.total_rounds }}</span>
              <span class="metric-lbl">{{ $tr('Rounds', '轮次', { de: 'Runden', fr: 'Tours' }) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-val">{{ data.sim1.total_actions.toLocaleString() }}</span>
              <span class="metric-lbl">{{ $tr('Actions', '动作', { de: 'Aktionen', fr: 'Actions' }) }}</span>
            </div>
          </div>
        </div>

        <div class="metric-card sim-b">
          <div class="metric-sim-id">{{ formatId(data.id2) }}</div>
          <div class="metric-grid">
            <div class="metric-item">
              <span class="metric-val">{{ data.sim2.profiles_count }}</span>
              <span class="metric-lbl">{{ $tr('Agents', '智能体', { de: 'Agenten', fr: 'Agents' }) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-val">{{ data.sim2.total_rounds }}</span>
              <span class="metric-lbl">{{ $tr('Rounds', '轮次', { de: 'Runden', fr: 'Tours' }) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-val">{{ data.sim2.total_actions.toLocaleString() }}</span>
              <span class="metric-lbl">{{ $tr('Actions', '动作', { de: 'Aktionen', fr: 'Actions' }) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Two-Column Layout -->
      <div class="two-col-layout">

        <!-- Influence Leaderboard Comparison -->
        <div class="cmp-section full-width">
          <div class="section-title">{{ $tr('Influence Leaderboard', '影响力榜单', { de: 'Einfluss-Rangliste', fr: `Classement d'influence` }) }}</div>
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
              <div v-if="!data.sim1.influence.length" class="lb-empty">{{ $tr('No data', '无数据', { de: 'Keine Daten', fr: 'Aucune donnée' }) }}</div>
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
              <div v-if="!data.sim2.influence.length" class="lb-empty">{{ $tr('No data', '无数据', { de: 'Keine Daten', fr: 'Aucune donnée' }) }}</div>
            </div>
          </div>
        </div>

        <!-- Activity Timeline Chart -->
        <div class="cmp-section full-width" v-if="data.sim1.timeline.length || data.sim2.timeline.length">
          <div class="section-title">{{ $tr('Activity per Round', '每轮活动量', { de: 'Aktivität pro Runde', fr: 'Activité par tour' }) }}</div>
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
                stroke="#a78bfa"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <!-- Sim B line -->
              <polyline
                v-if="chartPoints2.length > 1"
                :points="chartPoints2.map(p => `${p.x},${p.y}`).join(' ')"
                fill="none"
                stroke="#c4b5fd"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <!-- Dots Sim A -->
              <circle
                v-for="p in chartPoints1"
                :key="'a'+p.round"
                :cx="p.x" :cy="p.y" r="3"
                fill="#a78bfa"
              />
              <!-- Dots Sim B -->
              <circle
                v-for="p in chartPoints2"
                :key="'b'+p.round"
                :cx="p.x" :cy="p.y" r="3"
                fill="#c4b5fd"
              />
            </svg>
            <div class="chart-legend">
              <span class="legend-item sim-a-color">● {{ formatId(data.id1) }}</span>
              <span class="legend-item sim-b-color">● {{ formatId(data.id2) }}</span>
              <span class="legend-label">{{ $tr('Total actions / round', '每轮动作总数', { de: 'Aktionen gesamt / Runde', fr: 'Actions totales / tour' }) }}</span>
            </div>
          </div>
        </div>

        <!-- Market Prices (if available) -->
        <div
          class="cmp-section full-width"
          v-if="data.sim1.markets.length || data.sim2.markets.length"
        >
          <div class="section-title">{{ $tr('Prediction Market Final Prices', '预测市场最终价格', { de: 'Vorhersagemarkt-Endpreise', fr: 'Prix finaux du marché de prédiction' }) }}</div>
          <div class="markets-compare">
            <div class="market-col">
              <div class="market-col-header sim-a-color">{{ formatId(data.id1) }}</div>
              <div v-for="m in data.sim1.markets" :key="m.market_id" class="market-row">
                <span class="market-id">{{ $tr('Market', '市场', { de: 'Markt', fr: 'Marché' }) }} {{ m.market_id }}</span>
                <div class="market-bar-wrap">
                  <div class="market-bar" :style="{ width: (m.price_yes * 100) + '%', background: '#a78bfa' }"></div>
                </div>
                <span class="market-price">{{ (m.price_yes * 100).toFixed(1) }}% {{ $tr('YES', '是', { de: 'JA', fr: 'OUI' }) }}</span>
              </div>
            </div>
            <div class="market-col">
              <div class="market-col-header sim-b-color">{{ formatId(data.id2) }}</div>
              <div v-for="m in data.sim2.markets" :key="m.market_id" class="market-row">
                <span class="market-id">{{ $tr('Market', '市场', { de: 'Markt', fr: 'Marché' }) }} {{ m.market_id }}</span>
                <div class="market-bar-wrap">
                  <div class="market-bar" :style="{ width: (m.price_yes * 100) + '%', background: '#c4b5fd' }"></div>
                </div>
                <span class="market-price">{{ (m.price_yes * 100).toFixed(1) }}% {{ $tr('YES', '是', { de: 'JA', fr: 'OUI' }) }}</span>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="!loading && !error" class="cmp-empty">
      <p>{{ $tr('Select two simulations above and click Compare to see the diff.', '在上方选择两个模拟并点击对比以查看差异。', { de: 'Wählen Sie oben zwei Simulationen aus und klicken Sie auf Vergleichen, um die Unterschiede zu sehen.', fr: 'Sélectionnez deux simulations ci-dessus et cliquez sur Comparer pour voir les différences.' }) }}</p>
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
      error.value = res.data?.error || tr('Comparison failed', '对比失败', { de: 'Vergleich fehlgeschlagen', fr: 'Échec de la comparaison' })
    }
  } catch (err) {
    error.value = err?.response?.data?.error || err.message || tr('Comparison failed', '对比失败', { de: 'Vergleich fehlgeschlagen', fr: 'Échec de la comparaison' })
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
  if (s < 0.2) return tr('Simulations produced very similar influence rankings — comparable outcomes.', '两次模拟的影响力排名非常相似 — 结果可比。', { de: 'Simulationen erzeugten sehr ähnliche Einfluss-Rankings — vergleichbare Ergebnisse.', fr: 'Les simulations ont produit des classements d’influence très similaires - des résultats comparables.' })
  if (s < 0.5) return tr('Moderate divergence — some agents shifted in relative influence between runs.', '中等分歧 — 部分智能体在两次运行中相对影响力发生变化。', { de: 'Mäßige Divergenz — einige Agenten verschoben ihren relativen Einfluss zwischen den Läufen.' , fr: 'Divergence modérée — certains agents ont changé d\'influence relative.'})
  return tr('High divergence — the two simulations produced substantially different influence outcomes.', '高度分歧 — 两次模拟产生了截然不同的影响力结果。', { de: 'Hohe Divergenz — die zwei Simulationen erzeugten deutlich unterschiedliche Einflussergebnisse.' , fr: 'Divergence élevée — les deux simulations ont produit des résultats d\'influence très différents.'})
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
  if (label === '—') return tr('Not in other simulation\'s top 10', '不在另一次模拟的前 10 名中', { de: 'Nicht in den Top 10 der anderen Simulation' , fr: 'Pas dans le top 10 de l\'autre simulation'})
  if (label === '=') return tr('Same rank in both simulations', '两次模拟中排名相同', { de: 'Gleicher Rang in beiden Simulationen' , fr: 'Même rang dans les deux simulations'})
  return `${tr('Rank difference:', '排名差:', { de: 'Rangunterschied:' , fr: 'Différence de rang :'})} ${label.replace(/[▲▼]/, '')}`
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
  background:
    radial-gradient(circle at 18% 12%, rgba(139,92,246,0.18) 0%, transparent 55%),
    radial-gradient(circle at 82% 88%, rgba(76,29,149,0.22) 0%, transparent 60%),
    linear-gradient(180deg, #05030a 0%, #0a0518 100%);
  color: #f4f1ff;
  font-family: 'Geist Mono', ui-monospace, monospace;
}

.cmp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 32px;
  border-bottom: 1px solid rgba(167,139,250,0.16);
  background: linear-gradient(180deg, rgba(20,14,42,0.85) 0%, rgba(8,5,20,0.92) 100%);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  font-family: var(--font-sans);
  font-weight: 700;
  font-size: 1.05rem;
  letter-spacing: -0.01em;
  text-transform: none;
  color: #f4f1ff;
  cursor: pointer;
  transition: color 180ms ease;
}
.brand:hover { color: #c4b5fd; }
.brand-mark {
  width: 22px;
  height: 22px;
  object-fit: contain;
  filter: drop-shadow(0 4px 10px rgba(167, 139, 250, 0.5));
}
.page-tag {
  font-size: 11px;
  color: rgba(228,222,255,0.55);
  text-transform: uppercase;
  letter-spacing: 0.18em;
}
.download-btn {
  padding: 7px 16px;
  border: 1px solid rgba(167,139,250,0.22);
  background: linear-gradient(180deg, rgba(40,30,70,0.55) 0%, rgba(18,12,38,0.85) 100%);
  color: rgba(228,222,255,0.85);
  border-radius: 9999px;
  cursor: pointer;
  font-size: 12px;
  font-family: inherit;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
  transition: all 0.15s;
}
.download-btn:hover {
  border-color: #a78bfa;
  color: #a78bfa;
}

/* Selector Bar */
.selector-bar {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  padding: 20px 32px;
  border-bottom: 1px solid rgba(167,139,250,0.16);
  background: linear-gradient(180deg, rgba(20,14,42,0.6) 0%, rgba(8,5,20,0.85) 100%);
}
.selector-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}
.selector-label {
  font-size: 11px;
  color: rgba(228,222,255,0.55);
  text-transform: uppercase;
  letter-spacing: 0.18em;
}
.sim-select {
  padding: 10px 14px;
  background: linear-gradient(180deg, rgba(40,30,70,0.55) 0%, rgba(18,12,38,0.85) 100%);
  border: 1px solid rgba(167,139,250,0.18);
  color: #f4f1ff;
  border-radius: 10px;
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 12px;
  cursor: pointer;
  width: 100%;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.06);
  appearance: none;
  -webkit-appearance: none;
  background-image:
    linear-gradient(45deg, transparent 50%, rgba(228,222,255,0.6) 50%),
    linear-gradient(135deg, rgba(228,222,255,0.6) 50%, transparent 50%);
  background-position: calc(100% - 18px) 50%, calc(100% - 12px) 50%;
  background-size: 6px 6px, 6px 6px;
  background-repeat: no-repeat;
  padding-right: 32px;
}
.sim-select option {
  background: #0a0518;
  color: #f4f1ff;
}
.sim-select:focus {
  outline: none;
  border-color: rgba(167,139,250,0.55);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.1), 0 0 0 3px rgba(167,139,250,0.18);
}
.vs-badge {
  padding: 10px 16px;
  border: 1px solid rgba(167,139,250,0.22);
  background: linear-gradient(180deg, rgba(40,30,70,0.55) 0%, rgba(18,12,38,0.85) 100%);
  border-radius: 9999px;
  color: rgba(196,181,253,0.85);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.2em;
  flex-shrink: 0;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
}
.compare-btn {
  padding: 10px 26px;
  background: linear-gradient(180deg, rgba(167,139,250,0.55) 0%, rgba(76,29,149,0.75) 100%);
  color: #ffffff;
  border: 1px solid rgba(167,139,250,0.55);
  border-radius: 9999px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-family: inherit;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.2), 0 8px 22px -10px rgba(139,92,246,0.7);
  transition: transform 0.15s ease, box-shadow 0.15s ease, opacity 0.15s;
}
.compare-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.25), 0 12px 28px -10px rgba(139,92,246,0.8);
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
  border-top-color: #a78bfa;
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
.divergence-score.low { color: #c4b5fd; }
.divergence-score.medium { color: #FFB347; }
.divergence-score.high { color: #a78bfa; }
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
.metric-card.sim-a { border-top: 3px solid #a78bfa; }
.metric-card.sim-b { border-top: 3px solid #c4b5fd; }
.metric-sim-id { font-size: 11px; color: #555; margin-bottom: 12px; font-family: 'Geist Mono', monospace; }
.metric-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.metric-item { display: flex; flex-direction: column; gap: 4px; }
.metric-val { font-size: 20px; color: #110a26; font-weight: bold; }
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
  font-family: 'Geist Mono', monospace;
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
.delta-up { color: #c4b5fd; }
.delta-down { color: #a78bfa; }
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
.sim-a-color { color: #a78bfa; }
.sim-b-color { color: #c4b5fd; }

/* Markets */
.markets-compare { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.market-col { }
.market-col-header { font-size: 11px; font-family: 'Geist Mono', monospace; margin-bottom: 8px; }
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
