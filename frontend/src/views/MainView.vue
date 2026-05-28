<template>
  <div class="main-view">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">MIROSHARK</div>
      </div>
      
      <div class="header-center">
        <div class="view-switcher">
          <button
            v-for="mode in ['graph', 'split', 'workbench']"
            :key="mode"
            class="switch-btn"
            :class="{ active: viewMode === mode }"
            @click="viewMode = mode"
          >
            {{ viewModeLabel(mode) }}
          </button>
        </div>
      </div>

      <div class="header-right">
        <div class="workflow-step">
          <span class="step-num">{{ $tr('Step', '步骤') }} {{ currentStep }}/4</span>
          <span class="step-name">{{ stepName(currentStep - 1) }}</span>
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
          :currentPhase="currentPhase"
          @refresh="refreshGraph"
          @toggle-maximize="toggleMaximize('graph')"
        />
      </div>

      <!-- Right Panel: Step Components -->
      <div class="panel-wrapper right" :style="rightPanelStyle">
        <!-- Step 1: Graph Construction -->
        <Step1GraphBuild 
          v-if="currentStep === 1"
          :currentPhase="currentPhase"
          :projectData="projectData"
          :ontologyProgress="ontologyProgress"
          :buildProgress="buildProgress"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @next-step="handleNextStep"
        />
        <!-- Step 2: Agent Setup -->
        <Step2EnvSetup
          v-else-if="currentStep === 2"
          :projectData="projectData"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @go-back="handleGoBack"
          @next-step="handleNextStep"
          @add-log="addLog"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, watchEffect, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraphPanel from '../components/GraphPanel.vue'
import Step1GraphBuild from '../components/Step1GraphBuild.vue'
import Step2EnvSetup from '../components/Step2EnvSetup.vue'
import LocaleToggle from '../components/LocaleToggle.vue'
import { generateOntology, getProject, buildGraph, getTaskStatus, getGraphData } from '../api/graph'
import { getPendingUpload, clearPendingUpload } from '../store/pendingUpload'
import { tr } from '../i18n'

const route = useRoute()
const router = useRouter()

// Layout State
const viewMode = ref('split') // graph | split | workbench

// Step State
const currentStep = ref(1) // 1: Graph Construction, 2: Agent Setup, 3: Start Simulation, 4: Report Generation, 5: Deep Interaction
const stepNamesEn = ['Graph Construction', 'Agent Setup', 'Start Simulation', 'Report Generation']
const stepNamesZh = ['图谱构建', '智能体配置', '启动模拟', '生成报告']
const stepNames = stepNamesEn // legacy ref kept for handlers below
const stepName = (i) => tr(stepNamesEn[i] || '', stepNamesZh[i] || '')
const viewModeLabel = (mode) => {
  const en = { graph: 'Graph', split: 'Split', workbench: 'Workbench' }
  const zh = { graph: '图谱', split: '分屏', workbench: '工作台' }
  return tr(en[mode], zh[mode])
}

// Data State
const currentProjectId = ref(route.params.projectId)
const loading = ref(false)
const graphLoading = ref(false)
const error = ref('')
const projectData = ref(null)
const graphData = ref(null)
const currentPhase = ref(-1) // -1: Upload, 0: Ontology, 1: Build, 2: Complete
const ontologyProgress = ref(null)
const buildProgress = ref(null)
const systemLogs = ref([])

// Polling timers
let pollTimer = null
let graphPollTimer = null

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
  if (error.value) return 'error'
  if (currentPhase.value >= 2) return 'completed'
  if (currentPhase.value >= 0) return 'processing'
  return 'idle'
})

const statusText = computed(() => {
  if (error.value) return tr('Error', '错误')
  if (currentPhase.value >= 2) return tr('Ready', '就绪')
  if (currentPhase.value === 1) return tr('Building Graph', '构建图谱中')
  if (currentPhase.value === 0) return tr('Generating Ontology', '生成本体中')
  return tr('Idle', '空闲')
})

// --- Helpers ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  // Keep last 100 logs
  if (systemLogs.value.length > 100) {
    systemLogs.value.shift()
  }
}

// --- Layout Methods ---
const toggleMaximize = (target) => {
  if (viewMode.value === target) {
    viewMode.value = 'split'
  } else {
    viewMode.value = target
  }
}

const handleNextStep = (params = {}) => {
  if (currentStep.value < 4) {
    currentStep.value++
    addLog(`Entering Step ${currentStep.value}: ${stepNames[currentStep.value - 1]}`)
    
    // If entering Step 3 from Step 2, log the simulation round configuration
    if (currentStep.value === 3 && params.maxRounds) {
      addLog(`Custom simulation rounds: ${params.maxRounds} rounds`)
    }
  }
}

const handleGoBack = () => {
  if (currentStep.value > 1) {
    currentStep.value--
    addLog(`Returning to Step ${currentStep.value}: ${stepNames[currentStep.value - 1]}`)
  }
}

// --- Data Logic ---

const initProject = async () => {
  addLog('Project view initialized.')
  if (currentProjectId.value === 'new') {
    await handleNewProject()
  } else {
    await loadProject()
  }
}

const handleNewProject = async () => {
  const pending = getPendingUpload()
  const hasFiles = pending.files.length > 0
  const hasTemplate = !!pending.templateSeedText
  const hasUrlDocs = pending.urlDocs && pending.urlDocs.length > 0
  if (!pending.isPending || (!hasFiles && !hasTemplate && !hasUrlDocs)) {
    error.value = tr('No pending files found.', '没有待处理的文件。')
    addLog('Error: No pending files found for new project.')
    return
  }

  try {
    loading.value = true
    currentPhase.value = 0
    ontologyProgress.value = { message: 'Uploading and analyzing docs...' }
    addLog(hasTemplate
      ? `Starting from template "${pending.templateName}"...`
      : hasUrlDocs && !hasFiles
        ? `Starting from ${pending.urlDocs.length} URL document(s)...`
        : 'Starting ontology generation: Uploading files...')

    const formData = new FormData()
    if (hasFiles) {
      pending.files.forEach(f => formData.append('files', f))
    } else if (hasTemplate) {
      const blob = new Blob([pending.templateSeedText], { type: 'text/markdown' })
      const fileName = `${(pending.templateName || 'template').replace(/\s+/g, '_')}.md`
      formData.append('files', blob, fileName)
    }
    if (hasUrlDocs) {
      formData.append('url_docs', JSON.stringify(pending.urlDocs))
    }
    formData.append('simulation_requirement', pending.simulationRequirement)
    
    const res = await generateOntology(formData)
    if (res.success) {
      clearPendingUpload()
      currentProjectId.value = res.data.project_id
      projectData.value = res.data
      
      router.replace({ name: 'Process', params: { projectId: res.data.project_id } })
      ontologyProgress.value = null
      addLog(`Ontology generated successfully for project ${res.data.project_id}`)
      await startBuildGraph()
    } else {
      error.value = res.error || tr('Ontology generation failed', '本体生成失败')
      addLog(`Error generating ontology: ${error.value}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in handleNewProject: ${err.message}`)
  } finally {
    loading.value = false
  }
}

const loadProject = async () => {
  try {
    loading.value = true
    addLog(`Loading project ${currentProjectId.value}...`)
    const res = await getProject(currentProjectId.value)
    if (res.success) {
      projectData.value = res.data
      updatePhaseByStatus(res.data.status)
      addLog(`Project loaded. Status: ${res.data.status}`)
      
      if (res.data.status === 'ontology_generated' && !res.data.graph_id) {
        await startBuildGraph()
      } else if (res.data.status === 'graph_building' && res.data.graph_build_task_id) {
        currentPhase.value = 1
        startPollingTask(res.data.graph_build_task_id)
        startGraphPolling()
      } else if (res.data.status === 'graph_completed' && res.data.graph_id) {
        currentPhase.value = 2
        await loadGraph(res.data.graph_id)
      }
    } else {
      error.value = res.error
      addLog(`Error loading project: ${res.error}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in loadProject: ${err.message}`)
  } finally {
    loading.value = false
  }
}

const updatePhaseByStatus = (status) => {
  switch (status) {
    case 'created':
    case 'ontology_generated': currentPhase.value = 0; break;
    case 'graph_building': currentPhase.value = 1; break;
    case 'graph_completed': currentPhase.value = 2; break;
    case 'failed': error.value = tr('Project failed', '项目失败'); break;
  }
}

const startBuildGraph = async () => {
  try {
    currentPhase.value = 1
    buildProgress.value = { progress: 0, message: 'Starting build...' }
    addLog('Initiating graph build...')
    
    const res = await buildGraph({ project_id: currentProjectId.value })
    if (res.success) {
      addLog(`Graph build task started. Task ID: ${res.data.task_id}`)
      startGraphPolling()
      startPollingTask(res.data.task_id)
    } else {
      error.value = res.error
      addLog(`Error starting build: ${res.error}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in startBuildGraph: ${err.message}`)
  }
}

const startGraphPolling = () => {
  addLog('Started polling for graph data...')
  fetchGraphData()
  graphPollTimer = setInterval(fetchGraphData, 10000)
}

const fetchGraphData = async () => {
  try {
    // Refresh project info to check for graph_id
    const projRes = await getProject(currentProjectId.value)
    if (projRes.success && projRes.data.graph_id) {
      const gRes = await getGraphData(projRes.data.graph_id)
      if (gRes.success) {
        graphData.value = gRes.data
        const nodeCount = gRes.data.node_count || gRes.data.nodes?.length || 0
        const edgeCount = gRes.data.edge_count || gRes.data.edges?.length || 0
        addLog(`Graph data refreshed. Nodes: ${nodeCount}, Edges: ${edgeCount}`)
      }
    }
  } catch (err) {
    console.warn('Graph fetch error:', err)
  }
}

const startPollingTask = (taskId) => {
  pollTaskStatus(taskId)
  pollTimer = setInterval(() => pollTaskStatus(taskId), 2000)
}

const pollTaskStatus = async (taskId) => {
  try {
    const res = await getTaskStatus(taskId)
    if (res.success) {
      const task = res.data
      
      // Log progress message if it changed
      if (task.message && task.message !== buildProgress.value?.message) {
        addLog(task.message)
      }
      
      buildProgress.value = { progress: task.progress || 0, message: task.message }
      
      if (task.status === 'completed') {
        addLog('Graph build task completed.')
        stopPolling()
        stopGraphPolling() // Stop polling, do final load
        currentPhase.value = 2
        
        // Final load
        const projRes = await getProject(currentProjectId.value)
        if (projRes.success && projRes.data.graph_id) {
            projectData.value = projRes.data
            await loadGraph(projRes.data.graph_id)
        }
      } else if (task.status === 'failed') {
        stopPolling()
        error.value = task.error
        addLog(`Graph build task failed: ${task.error}`)
      }
    }
  } catch (e) {
    console.error(e)
  }
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  addLog(`Loading full graph data: ${graphId}`)
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      addLog('Graph data loaded successfully.')
    } else {
      addLog(`Failed to load graph data: ${res.error}`)
    }
  } catch (e) {
    addLog(`Exception loading graph: ${e.message}`)
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    addLog('Manual graph refresh triggered.')
    loadGraph(projectData.value.graph_id)
  }
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const stopGraphPolling = () => {
  if (graphPollTimer) {
    clearInterval(graphPollTimer)
    graphPollTimer = null
    addLog('Graph polling stopped.')
  }
}

watchEffect(() => {
  const step = currentStep.value
  const status = statusClass.value
  const dot = status === 'processing' ? '\uD83D\uDFE0' : status === 'error' ? '\uD83D\uDD34' : status === 'completed' ? '\uD83D\uDFE2' : ''
  document.title = dot ? `${dot} (${step}/4) MiroShark` : `(${step}/4) MiroShark`
})

onMounted(() => {
  initProject()
})

onUnmounted(() => {
  document.title = 'MiroShark'
  stopPolling()
  stopGraphPolling()
})
</script>

<style scoped>
/* MiroShark deep-space-violet — Process shell.
   Local tokens kept for the few rules below that still reference them,
   but flipped to match the App.vue palette so descendants inherit the
   correct semantics. */
.main-view {
  --color-orange: #a78bfa;
  --color-green:  #c4b5fd;
  --color-white:  #110a26;
  --color-black:  #f4f1ff;
  --color-gray:   #1a0f3a;
  --color-red:    #f0abfc;
  --color-amber:  #fcd34d;
  --font-display: 'Geist', system-ui, -apple-system, sans-serif;
  --font-mono:    'Geist Mono', ui-monospace, 'SF Mono', Menlo, monospace;
  --border-light: 1px solid rgba(255,255,255,0.08);
  --border-medium: 1px solid rgba(167,139,250,0.18);
  --space-xs: 6px;
  --space-sm: 11px;
  --space-md: 22px;
  --space-lg: 34px;
  --space-xl: 56px;
}

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

/* Header — sticky glossy bar matching Home navbar. */
.app-header {
  height: 60px;
  border-bottom: 1px solid rgba(167,139,250,0.16);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-md);
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
  font-family: var(--font-mono);
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 3px;
  cursor: pointer;
  text-transform: uppercase;
  background: linear-gradient(180deg, #ffffff 0%, #e4ddff 45%, #c4b5fd 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
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
  border: none;
  background: transparent;
  padding: 6px 14px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: rgba(228,222,255,0.55);
  text-transform: uppercase;
  letter-spacing: 2px;
  cursor: pointer;
  border-radius: 9999px;
  transition: color 180ms ease, background 180ms ease;
}

.switch-btn:hover {
  color: #ffffff;
}

.switch-btn.active {
  background: linear-gradient(180deg, rgba(167,139,250,0.35) 0%, rgba(76,29,149,0.55) 100%);
  color: #ffffff;
  border: 1px solid rgba(167,139,250,0.45);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.18), 0 6px 16px -10px rgba(139,92,246,0.7);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(228,222,255,0.6);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 2px;
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
  background-color: rgba(255,255,255,0.12);
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(228,222,255,0.25);
  box-shadow: 0 0 8px rgba(228,222,255,0.2);
}

.status-indicator.processing .dot { background: var(--color-orange); animation: pulse 1s infinite; }
.status-indicator.completed .dot { background: var(--color-green); }
.status-indicator.idle .dot { background: var(--color-amber); }
.status-indicator.error .dot { background: var(--color-red); }

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
  border-right: 1px solid rgba(167,139,250,0.14);
}
</style>
