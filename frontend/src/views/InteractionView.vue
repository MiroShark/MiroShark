<template>
  <div class="main-view">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">
          <img src="/shark.webp" alt="" class="brand-mark" />
          <span>MiroShark</span>
        </div>
      </div>
      
      <div class="header-center">
        <div class="view-switcher">
          <button
            v-for="mode in ['graph', 'workbench']"
            :key="mode"
            class="switch-btn"
            :class="{ active: viewMode === mode }"
            @click="viewMode = mode"
          >
            {{ { graph: $tr('Graph', '图谱', { de: 'Graph', fr: 'Graphe' }), workbench: $tr('Workbench', '工作台', { de: 'Arbeitsbereich', fr: 'Atelier' }) }[mode] }}
          </button>
        </div>
      </div>

      <div class="header-right">
        <div class="workflow-step">
          <span class="step-num">{{ $tr('Step 4/4', '第 4/4 步', { de: 'Schritt 4/4', fr: 'Étape 4/4' }) }}</span>
          <span class="step-name">{{ $tr('Deep Interaction', '深度交互', { de: 'Tiefe Interaktion', fr: 'Interaction approfondie' }) }}</span>
        </div>
        <div class="step-divider"></div>
        <span class="status-indicator" :class="statusClass">
          <span class="dot"></span>
          {{ statusText }}
        </span>
        <LocaleToggle />
      </div>
    </header>

    <!-- Main Content Area -->
    <main class="content-area">
      <!-- Left Panel: Graph -->
      <div class="panel-wrapper left" :style="leftPanelStyle">
        <GraphPanel
          :graphData="graphData"
          :loading="graphLoading"
          :currentPhase="5"
          :isSimulating="false"
          :simulationId="simulationId"
          @refresh="refreshGraph"
          @toggle-maximize="toggleMaximize('graph')"
        />
      </div>

      <!-- Right Panel: Step5 Deep Interaction -->
      <div class="panel-wrapper right" :style="rightPanelStyle">
        <Step5Interaction
          :reportId="currentReportId"
          :simulationId="simulationId"
          :systemLogs="systemLogs"
          @add-log="addLog"
          @update-status="updateStatus"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, watchEffect, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraphPanel from '../components/GraphPanel.vue'
import Step5Interaction from '../components/Step5Interaction.vue'
import LocaleToggle from '../components/LocaleToggle.vue'
import { tr } from '../i18n'
import { getProject, getGraphData } from '../api/graph'
import { getSimulation } from '../api/simulation'
import { getReport } from '../api/report'

const route = useRoute()
const router = useRouter()

// Props
const props = defineProps({
  reportId: String
})

// Layout State - default to workbench (no split on report/interaction)
const viewMode = ref('workbench')

// Data State
const currentReportId = ref(route.params.reportId)
const simulationId = ref(null)
const projectData = ref(null)
const graphData = ref(null)
const graphLoading = ref(false)
const systemLogs = ref([])
const currentStatus = ref('ready') // ready | processing | completed | error

// --- Computed Layout Styles ---
const leftPanelStyle = computed(() => {
  if (viewMode.value === 'graph') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'workbench') return { width: '0%', opacity: 0, transform: 'translateX(-20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

const rightPanelStyle = computed(() => {
  if (viewMode.value === 'workbench') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'graph') return { width: '0%', opacity: 0, transform: 'translateX(20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

// --- Status Computed ---
const statusClass = computed(() => {
  return currentStatus.value
})

const statusText = computed(() => {
  if (currentStatus.value === 'error') return tr('Error', '错误', { de: 'Fehler', fr: 'Erreur' })
  if (currentStatus.value === 'completed') return tr('Completed', '已完成', { de: 'Abgeschlossen', fr: 'Terminé' })
  if (currentStatus.value === 'processing') return tr('Processing', '处理中', { de: 'Wird verarbeitet', fr: 'Traitement en cours' })
  return tr('Ready', '就绪', { de: 'Bereit', fr: 'Prêt' })
})

// --- Helpers ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  if (systemLogs.value.length > 200) {
    systemLogs.value.shift()
  }
}

const updateStatus = (status) => {
  currentStatus.value = status
}

// --- Layout Methods ---
const toggleMaximize = (target) => {
  if (viewMode.value === target) {
    viewMode.value = 'workbench'
  } else {
    viewMode.value = target
  }
}

// --- Data Logic ---
const loadReportData = async () => {
  try {
    addLog(`Loading report data: ${currentReportId.value}`)
    
    // Get report info to obtain simulation_id
    const reportRes = await getReport(currentReportId.value)
    if (reportRes.success && reportRes.data) {
      const reportData = reportRes.data
      simulationId.value = reportData.simulation_id

      if (simulationId.value) {
        // Get simulation info
        const simRes = await getSimulation(simulationId.value)
        if (simRes.success && simRes.data) {
          const simData = simRes.data

          // Get project info
          if (simData.project_id) {
            const projRes = await getProject(simData.project_id)
            if (projRes.success && projRes.data) {
              projectData.value = projRes.data
              addLog(`Project loaded successfully: ${projRes.data.project_id}`)

              // Get graph data
              if (projRes.data.graph_id) {
                await loadGraph(projRes.data.graph_id)
              }
            }
          }
        }
      }
    } else {
      addLog(`Failed to get report info: ${reportRes.error || 'Unknown error'}`)
    }
  } catch (err) {
    addLog(`Loading exception: ${err.message}`)
  }
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      addLog('Graph data loaded successfully')
    }
  } catch (err) {
    addLog(`Graph loading failed: ${err.message}`)
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    loadGraph(projectData.value.graph_id)
  }
}

// Watch route params
watch(() => route.params.reportId, (newId) => {
  if (newId && newId !== currentReportId.value) {
    currentReportId.value = newId
    loadReportData()
  }
}, { immediate: true })

watchEffect(() => {
  const status = statusClass.value
  const dot = status === 'processing' ? '\uD83D\uDFE0' : status === 'error' ? '\uD83D\uDD34' : status === 'completed' ? '\uD83D\uDFE2' : ''
  document.title = dot ? `${dot} (4/4) MiroShark` : '(4/4) MiroShark'
})

onUnmounted(() => { document.title = 'MiroShark' })

onMounted(() => {
  addLog('InteractionView initialized')
  loadReportData()
})
</script>

<style scoped>
.main-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(circle at 18% 12%, rgba(139,92,246,0.18) 0%, transparent 55%),
    radial-gradient(circle at 82% 88%, rgba(76,29,149,0.22) 0%, transparent 60%),
    linear-gradient(180deg, #05030a 0%, #0a0518 100%);
  color: #f4f1ff;
  overflow: hidden;
  font-family: var(--font-display);
}

/* Header */
.app-header {
  height: 60px;
  border-bottom: 1px solid rgba(167,139,250,0.16);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px;
  background: linear-gradient(180deg, rgba(20,14,42,0.85) 0%, rgba(8,5,20,0.92) 100%);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  color: #f4f1ff;
  z-index: 100;
  position: relative;
  box-shadow: inset 0 -1px 0 rgba(255,255,255,0.04), 0 8px 32px -16px rgba(0,0,0,0.6);
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
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

.view-switcher {
  display: flex;
  background: linear-gradient(180deg, rgba(40,30,70,0.55) 0%, rgba(18,12,38,0.75) 100%);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 9999px;
  padding: 4px;
  gap: 2px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
}

.switch-btn {
  border: 1px solid transparent;
  background: transparent;
  padding: 6px 14px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: rgba(228,222,255,0.55);
  cursor: pointer;
  border-radius: 9999px;
  transition: color 180ms ease, background 180ms ease;
}
.switch-btn:hover { color: #ffffff; }

.switch-btn.active {
  background: linear-gradient(180deg, rgba(167,139,250,0.35) 0%, rgba(76,29,149,0.55) 100%);
  color: #ffffff;
  border: 1px solid rgba(167,139,250,0.55);
  border-radius: 9999px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.18), 0 6px 16px -10px rgba(139,92,246,0.7);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.step-num {
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: rgba(196,181,253,0.65);
}

.step-name {
  font-weight: 600;
  font-size: 13px;
  color: #f4f1ff;
}

.step-divider {
  width: 1px;
  height: 14px;
  background-color: rgba(250,250,250,0.12);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 3px;
  color: rgba(250,250,250,0.5);
  font-weight: 500;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(250,250,250,0.2);
}

.status-indicator.ready .dot { background: #c4b5fd; }
.status-indicator.processing .dot { background: #a78bfa; animation: pulse 1s infinite; }
.status-indicator.completed .dot { background: #c4b5fd; }
.status-indicator.idle .dot { background: #FFB347; }
.status-indicator.error .dot { background: #FF4444; }

@keyframes pulse { 50% { opacity: 0.5; } }

/* Content */
.content-area {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
}

.panel-wrapper {
  height: 100%;
  overflow: hidden;
  transition: width 0.4s cubic-bezier(0.25, 0.8, 0.25, 1), opacity 0.3s ease, transform 0.3s ease;
  will-change: width, opacity, transform;
}

.panel-wrapper.left {
  border-right: 2px solid rgba(10,10,10,0.08);
}
</style>
