<template>
  <div class="decision-lab">
    <!-- Header -->
    <header class="lab-header">
      <div class="brand" @click="$router.push('/')">MIROSHARK</div>
      <div class="project-nav" v-if="lab?.project_id || selectedProjectId">
        <router-link
          :to="{ name: 'Process', params: { projectId: lab?.project_id || selectedProjectId }}"
          class="nav-tab"
        >Pipeline</router-link>
        <span class="nav-tab active">Decision Lab</span>
      </div>
      <div v-else class="lab-title">Decision Lab</div>
      <div class="lab-status-badge" :class="lab?.status || 'empty'">
        {{ lab?.status || 'new' }}
      </div>
    </header>

    <main class="lab-content">
      <!-- Left: Scenario Setup -->
      <section class="setup-panel">
        <div v-if="initialLoading" class="loading-state">Loading lab...</div>
        <!-- Project Selection (if no lab yet) -->
        <div v-else-if="!lab" class="setup-section">
          <h2 class="section-label">01 / Select Project</h2>
          <p class="section-desc">Choose a project with a completed knowledge graph.</p>
          <select v-model="selectedProjectId" class="project-select" :disabled="creating">
            <option value="">-- Select Project --</option>
            <option v-for="proj in projects" :key="proj.project_id" :value="proj.project_id">
              {{ proj.name }} ({{ proj.project_id }})
            </option>
          </select>
          <div class="input-group">
            <label class="input-label">Lab Name</label>
            <input v-model="labName" class="text-input" placeholder="e.g. Iran Conflict Decision Analysis" :disabled="creating" />
          </div>
          <button class="action-btn" @click="handleCreateLab" :disabled="!selectedProjectId || creating">
            {{ creating ? 'Creating...' : 'Create Decision Lab' }}
          </button>
        </div>

        <!-- Branch Definition -->
        <div v-if="lab" class="setup-section">
          <h2 class="section-label">02 / Decision Branches</h2>
          <p class="section-desc">Define 2-5 decision scenarios to compare.</p>

          <!-- Existing branches -->
          <div v-for="branch in lab.branches" :key="branch.branch_id" class="branch-card">
            <div class="branch-header">
              <span class="branch-label">{{ branch.label }}</span>
              <span class="branch-status" :class="branch.status">{{ branch.status }}</span>
            </div>
            <p class="branch-text">{{ branch.decision_text }}</p>
            <button
              v-if="branch.status === 'pending'"
              class="remove-btn"
              @click="handleRemoveBranch(branch.branch_id)"
            >&times;</button>
          </div>

          <!-- Add new branch form -->
          <div v-if="canAddBranch" class="add-branch-form">
            <input v-model="newBranchLabel" class="text-input" placeholder="Label (e.g. Sanctions)" />
            <textarea v-model="newBranchText" class="text-area" placeholder="Decision scenario text..." rows="3"></textarea>
            <button class="action-btn secondary" @click="handleAddBranch" :disabled="!newBranchLabel.trim() || !newBranchText.trim()">
              + Add Branch
            </button>
          </div>
        </div>

        <!-- Actions -->
        <div v-if="lab && lab.branches.length >= 2" class="setup-section">
          <h2 class="section-label">03 / Execute</h2>
          <button
            v-if="lab.status === 'created'"
            class="action-btn"
            @click="handlePrepare"
            :disabled="preparing"
          >
            {{ preparing ? 'Preparing branches...' : 'Prepare All Branches' }}
          </button>
          <button
            v-if="lab.status === 'ready'"
            class="action-btn"
            @click="handleRun"
            :disabled="running"
          >
            {{ running ? 'Starting...' : 'Run All Simulations' }}
          </button>
          <div v-if="lab.status === 'preparing'" class="status-msg">
            Preparing branches... polling for updates.
          </div>
          <div v-if="lab.status === 'running'" class="status-msg">
            Simulations running. See progress on the right.
          </div>
          <button
            v-if="lab.status === 'completed' || lab.status === 'running'"
            class="action-btn secondary"
            @click="handleCompare"
            :disabled="comparing"
            style="margin-top: 8px"
          >
            {{ comparing ? 'Comparing...' : 'Compare Branches' }}
          </button>
        </div>

        <!-- Autonomous Optimizer -->
        <div v-if="lab && lab.branches.length >= 1" class="setup-section">
          <h2 class="section-label">04 / Autonomous Optimizer</h2>
          <p class="section-desc">Set a goal — AI proposes, tests, and refines strategies overnight.</p>
          <input
            v-model="autoGoal"
            class="text-input"
            placeholder="e.g. Find the decision that minimizes escalation risk"
            :disabled="autoRunning"
          />
          <div class="auto-config">
            <label class="input-label">Iterations
              <input v-model.number="autoIterations" type="number" min="1" max="20" class="num-input" :disabled="autoRunning" />
            </label>
            <label class="input-label">Rounds/sim
              <input v-model.number="autoRounds" type="number" min="5" max="72" class="num-input" :disabled="autoRunning" />
            </label>
          </div>
          <button
            v-if="!autoRunning"
            class="action-btn"
            @click="handleStartAuto"
            :disabled="!autoGoal.trim()"
          >
            Start Autonomous Optimization
          </button>
          <button v-else class="action-btn secondary" @click="handleStopAuto">
            Stop After Current Iteration
          </button>
          <div v-if="autoState" class="auto-status">
            <div class="auto-progress">
              Iteration {{ autoState.current_iteration }} / {{ autoState.max_iterations }}
              <span class="auto-status-badge" :class="autoState.status">{{ autoState.status }}</span>
            </div>
            <div v-if="autoState.best_strategy" class="auto-best">
              Best so far: <strong>{{ autoState.best_strategy.label }}</strong>
              (score {{ autoState.best_strategy.score }}/10)
              <p class="auto-reasoning">{{ autoState.best_strategy.reasoning }}</p>
            </div>
            <div v-for="(result, idx) in autoState.results" :key="idx" class="auto-iteration-card">
              <div class="auto-iter-header">Iteration {{ result.iteration }}</div>
              <div v-for="branch in result.branches" :key="branch.label" class="auto-branch-result">
                <span class="auto-verdict" :class="branch.verdict.toLowerCase()">{{ branch.verdict }}</span>
                <span class="auto-branch-label">{{ branch.label }}</span>
                <span class="auto-branch-score">{{ branch.score }}/10</span>
              </div>
            </div>
          </div>
        </div>

        <!-- What-If Injection -->
        <div v-if="lab && lab.status !== 'created'" class="setup-section">
          <h2 class="section-label">05 / What-If Injection</h2>
          <p class="section-desc">Add new information and re-run to see how outcomes change.</p>
          <textarea
            v-model="injectText"
            class="text-area"
            placeholder="e.g. Russia announces joint military exercises with Iran in the Strait of Hormuz"
            rows="3"
          ></textarea>
          <button
            class="action-btn"
            @click="handleInject"
            :disabled="!injectText.trim() || injecting"
          >
            {{ injecting ? 'Injecting...' : 'Inject & Re-run' }}
          </button>
        </div>
      </section>

      <!-- Right: Branch Progress -->
      <section class="progress-panel">
        <h2 class="section-label">Branch Progress</h2>
        <div v-if="!lab" class="empty-state">Create a lab and add branches to begin.</div>
        <div v-else-if="lab.branches.length === 0" class="empty-state">No branches defined yet.</div>
        <div v-else class="branch-progress-list">
          <div v-for="branch in branchDetails" :key="branch.branch_id" class="progress-card">
            <div class="progress-header">
              <span class="progress-label">{{ branch.label }}</span>
              <span class="progress-status" :class="branch.status">{{ branch.status }}</span>
            </div>
            <div v-if="branch.simulation_id" class="progress-sim-id mono">{{ branch.simulation_id }}</div>
            <div v-if="branch.current_round !== undefined" class="progress-bar-container">
              <div class="progress-bar" :style="{ width: progressPercent(branch) + '%' }"></div>
              <span class="progress-text">Round {{ branch.current_round || 0 }} / {{ branch.total_rounds || 72 }}</span>
            </div>
            <div v-if="branch.twitter_actions || branch.reddit_actions" class="progress-actions">
              <span v-if="branch.twitter_actions">Twitter: {{ branch.twitter_actions }}</span>
              <span v-if="branch.reddit_actions">Reddit: {{ branch.reddit_actions }}</span>
            </div>
            <div v-if="branch.error" class="progress-error">{{ branch.error }}</div>
            <button
              v-if="branch.status === 'completed' && branch.simulation_id"
              class="consequence-btn"
              @click="loadConsequences(branch)"
            >
              View Consequence Tree
            </button>
          </div>
        </div>

        <!-- Comparison Dashboard -->
        <div v-if="comparisonData" class="comparison-section">
          <h2 class="section-label">Branch Comparison</h2>
          <div class="comparison-grid">
            <div v-for="(metrics, label) in comparisonData.branches" :key="label" class="comparison-card">
              <div class="comparison-label">{{ label }}</div>
              <div class="comparison-stats">
                <div class="comp-stat">
                  <span class="comp-value">{{ metrics.total_posts }}</span>
                  <span class="comp-key">Posts</span>
                </div>
                <div class="comp-stat">
                  <span class="comp-value">{{ metrics.total_comments }}</span>
                  <span class="comp-key">Comments</span>
                </div>
                <div class="comp-stat">
                  <span class="comp-value">{{ metrics.engagement_rate }}</span>
                  <span class="comp-key">Engagement</span>
                </div>
                <div class="comp-stat">
                  <span class="comp-value">{{ metrics.active_agents }}</span>
                  <span class="comp-key">Active Agents</span>
                </div>
                <div class="comp-stat">
                  <span class="comp-value">{{ metrics.total_likes - metrics.total_dislikes }}</span>
                  <span class="comp-key">Net Sentiment</span>
                </div>
              </div>
              <div class="comp-top-posters" v-if="metrics.top_posters?.length">
                <span class="comp-key">Top posters:</span>
                <span v-for="([name, count], idx) in metrics.top_posters" :key="idx" class="top-poster">
                  {{ name }} ({{ count }})
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Consequence Tree -->
        <div v-if="activeConsequenceTree" class="consequence-section">
          <h2 class="section-label">Consequence Tree — {{ activeConsequenceBranch }}</h2>
          <ConsequenceTree :tree-data="activeConsequenceTree" :loading="loadingConsequences" />
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getProject } from '../api/graph'
import {
  createLab, getLab, listLabs, addBranch, removeBranch,
  prepareLab, runLab, getLabStatus
} from '../api/decisionLab'
import ConsequenceTree from '../components/ConsequenceTree.vue'
import service from '../api/index'

const route = useRoute()
const router = useRouter()

const lab = ref(null)
const projects = ref([])
const selectedProjectId = ref('')
const labName = ref('')
const creating = ref(false)
const initialLoading = ref(true)
const preparing = ref(false)
const running = ref(false)
const newBranchLabel = ref('')
const newBranchText = ref('')
const branchDetails = ref([])

const autoGoal = ref('')
const autoIterations = ref(5)
const autoRounds = ref(20)
const autoRunning = ref(false)
const autoState = ref(null)
let autoPollTimer = null

const handleStartAuto = async () => {
  autoRunning.value = true
  try {
    const res = await service({
      url: `/api/decision-lab/${lab.value.lab_id}/auto/start`,
      method: 'post',
      data: {
        goal: autoGoal.value.trim(),
        max_iterations: autoIterations.value,
        max_rounds_per_sim: autoRounds.value,
      }
    })
    if (res.success) {
      autoState.value = res.data
      startAutoPoll()
    }
  } catch (_err) {
    autoRunning.value = false
  }
}

const handleStopAuto = async () => {
  await service({
    url: `/api/decision-lab/${lab.value.lab_id}/auto/stop`,
    method: 'post'
  })
}

const pollAutoStatus = async () => {
  if (!lab.value) return
  try {
    const res = await service({
      url: `/api/decision-lab/${lab.value.lab_id}/auto/status`,
      method: 'get'
    })
    if (res.success) {
      autoState.value = res.data
      if (res.data.status === 'completed' || res.data.status === 'failed') {
        autoRunning.value = false
        stopAutoPoll()
      }
    }
  } catch (_err) { /* silent */ }
}

const startAutoPoll = () => {
  stopAutoPoll()
  autoPollTimer = setInterval(pollAutoStatus, 10000)
}

const stopAutoPoll = () => {
  if (autoPollTimer) {
    clearInterval(autoPollTimer)
    autoPollTimer = null
  }
}

const comparisonData = ref(null)
const comparing = ref(false)
const injectText = ref('')
const injecting = ref(false)

const handleCompare = async () => {
  comparing.value = true
  try {
    const res = await service({
      url: `/api/decision-lab/${lab.value.lab_id}/compare`,
      method: 'get'
    })
    if (res.success) comparisonData.value = res.data
  } finally {
    comparing.value = false
  }
}

const handleInject = async () => {
  injecting.value = true
  try {
    const res = await service({
      url: `/api/decision-lab/${lab.value.lab_id}/inject`,
      method: 'post',
      data: { info_text: injectText.value.trim() }
    })
    if (res.success) {
      injectText.value = ''
      await loadLab(lab.value.lab_id)
      startPolling()
    }
  } finally {
    injecting.value = false
  }
}

const activeConsequenceTree = ref(null)
const activeConsequenceBranch = ref('')
const loadingConsequences = ref(false)

const loadConsequences = async (branch) => {
  loadingConsequences.value = true
  activeConsequenceBranch.value = branch.label
  activeConsequenceTree.value = null
  try {
    const res = await service({
      url: `/api/decision-lab/${lab.value.lab_id}/consequences/${branch.branch_id}`,
      method: 'get'
    })
    if (res.success) {
      activeConsequenceTree.value = res.data
    }
  } finally {
    loadingConsequences.value = false
  }
}

let pollTimer = null

const canAddBranch = computed(() => {
  if (!lab.value) return false
  if (lab.value.branches.length >= 5) return false
  return lab.value.status === 'created'
})

const progressPercent = (branch) => {
  const total = branch.total_rounds || 72
  const current = branch.current_round || 0
  return Math.round((current / total) * 100)
}

const loadProjects = async () => {
  try {
    const res = await fetch('/api/simulation/history?limit=50')
    const data = await res.json()
    if (data.data) {
      projects.value = data.data.filter(p => p.project_id)
    }
  } catch (_err) { /* silent */ }
}

const loadLab = async (labId) => {
  const res = await getLab(labId)
  if (res.success) {
    lab.value = res.data
    branchDetails.value = res.data.branches
  }
}

const handleCreateLab = async () => {
  creating.value = true
  try {
    const res = await createLab({
      project_id: selectedProjectId.value,
      name: labName.value || 'Decision Lab',
    })
    if (res.success) {
      lab.value = res.data
      branchDetails.value = res.data.branches
      router.replace({ params: { labId: res.data.lab_id } })
    }
  } finally {
    creating.value = false
  }
}

const handleAddBranch = async () => {
  const res = await addBranch(lab.value.lab_id, {
    label: newBranchLabel.value.trim(),
    decision_text: newBranchText.value.trim(),
  })
  if (res.success) {
    lab.value = res.data.lab
    branchDetails.value = res.data.lab.branches
    newBranchLabel.value = ''
    newBranchText.value = ''
  }
}

const handleRemoveBranch = async (branchId) => {
  const res = await removeBranch(lab.value.lab_id, branchId)
  if (res.success) {
    lab.value = res.data
    branchDetails.value = res.data.branches
  }
}

const handlePrepare = async () => {
  preparing.value = true
  try {
    await prepareLab(lab.value.lab_id)
    startPolling()
  } finally {
    preparing.value = false
  }
}

const handleRun = async () => {
  running.value = true
  try {
    await runLab(lab.value.lab_id)
    startPolling()
  } finally {
    running.value = false
  }
}

const pollStatus = async () => {
  if (!lab.value) return
  const res = await getLabStatus(lab.value.lab_id)
  if (res.success) {
    lab.value.status = res.data.status
    branchDetails.value = res.data.branches
    if (res.data.status === 'completed' || res.data.status === 'failed') {
      stopPolling()
    }
  }
}

const startPolling = () => {
  stopPolling()
  pollTimer = setInterval(pollStatus, 3000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(async () => {
  const labId = route.params.labId
  if (labId && labId !== 'new') {
    await loadLab(labId)
    if (lab.value && ['preparing', 'running'].includes(lab.value.status)) {
      startPolling()
    }
  } else {
    await loadProjects()
    // Auto-select project if coming from Pipeline tab
    const projectFromQuery = route.query.project
    if (projectFromQuery) {
      selectedProjectId.value = projectFromQuery
    }
  }
  initialLoading.value = false
})

onUnmounted(() => {
  stopPolling()
  stopAutoPoll()
})
</script>

<style scoped>
.decision-lab {
  height: 100vh;
  display: flex;
  flex-direction: column;
  font-family: 'Space Grotesk', system-ui, sans-serif;
  background: #fff;
}

.lab-header {
  height: 60px;
  border-bottom: 1px solid #eaeaea;
  display: flex;
  align-items: center;
  padding: 0 24px;
  gap: 16px;
}

.brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 1px;
  cursor: pointer;
}

.lab-title {
  font-weight: 600;
  font-size: 14px;
  color: #666;
}

.project-nav {
  display: flex;
  gap: 4px;
  background: #F5F5F5;
  padding: 4px;
  border-radius: 6px;
}

.nav-tab {
  padding: 5px 14px;
  font-size: 11px;
  font-weight: 600;
  color: #666;
  text-decoration: none;
  border-radius: 4px;
  transition: all 0.2s;
  cursor: pointer;
}

.nav-tab:hover { color: #333; background: #eee; }
.nav-tab.active { background: #fff; color: #000; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }

.lab-status-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  padding: 3px 8px;
  border-radius: 3px;
  background: #f0f0f0;
  color: #666;
}
.lab-status-badge.ready { background: #e8f5e9; color: #2e7d32; }
.lab-status-badge.running { background: #fff3e0; color: #e65100; }
.lab-status-badge.completed { background: #e8f5e9; color: #1a936f; }
.lab-status-badge.failed { background: #ffebee; color: #c62828; }
.lab-status-badge.preparing { background: #fff3e0; color: #e65100; }

.lab-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.setup-panel {
  width: 50%;
  padding: 24px;
  overflow-y: auto;
  border-right: 1px solid #eaeaea;
}

.progress-panel {
  width: 50%;
  padding: 24px;
  overflow-y: auto;
}

.section-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.section-desc {
  font-size: 12px;
  color: #666;
  margin-bottom: 16px;
}

.setup-section {
  margin-bottom: 32px;
}

.project-select, .text-input, .text-area {
  width: 100%;
  border: 1px solid #ddd;
  padding: 10px 12px;
  font-size: 13px;
  font-family: 'JetBrains Mono', monospace;
  border-radius: 4px;
  background: #fafafa;
  margin-bottom: 10px;
}

.text-area {
  resize: vertical;
  min-height: 60px;
}

.input-group {
  margin-bottom: 10px;
}

.input-label {
  font-size: 11px;
  font-weight: 600;
  color: #999;
  display: block;
  margin-bottom: 4px;
}

.action-btn {
  width: 100%;
  background: #000;
  color: #fff;
  border: none;
  padding: 14px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}
.action-btn:hover:not(:disabled) { opacity: 0.8; }
.action-btn:disabled { background: #ccc; cursor: not-allowed; }
.action-btn.secondary { background: #f5f5f5; color: #333; border: 1px solid #ddd; }
.action-btn.secondary:hover:not(:disabled) { background: #e0e0e0; }

.branch-card {
  border: 1px solid #eaeaea;
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 8px;
  position: relative;
}

.branch-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.branch-label {
  font-weight: 600;
  font-size: 13px;
}

.branch-status {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 3px;
  background: #f0f0f0;
  color: #666;
}
.branch-status.ready { background: #e8f5e9; color: #2e7d32; }
.branch-status.running { background: #fff3e0; color: #e65100; }
.branch-status.completed { background: #e8f5e9; color: #1a936f; }
.branch-status.failed { background: #ffebee; color: #c62828; }
.branch-status.preparing { background: #fff3e0; color: #e65100; }

.branch-text {
  font-size: 12px;
  color: #666;
  line-height: 1.5;
}

.remove-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  background: none;
  border: none;
  font-size: 18px;
  color: #ccc;
  cursor: pointer;
}
.remove-btn:hover { color: #c62828; }

.add-branch-form {
  border: 1px dashed #ddd;
  border-radius: 6px;
  padding: 12px;
  margin-top: 8px;
}

.status-msg {
  font-size: 12px;
  color: #e65100;
  padding: 12px;
  background: #fff3e0;
  border-radius: 4px;
}

.loading-state {
  text-align: center;
  padding: 40px;
  color: #999;
  font-size: 13px;
}

.empty-state {
  color: #999;
  font-size: 13px;
  text-align: center;
  padding: 40px;
}

.progress-card {
  border: 1px solid #eaeaea;
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 12px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.progress-label { font-weight: 600; font-size: 14px; }
.progress-status {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 3px;
  background: #f0f0f0;
  color: #666;
}
.progress-status.ready { background: #e8f5e9; color: #2e7d32; }
.progress-status.running { background: #fff3e0; color: #e65100; }
.progress-status.completed { background: #e8f5e9; color: #1a936f; }
.progress-status.failed { background: #ffebee; color: #c62828; }
.progress-status.preparing { background: #fff3e0; color: #e65100; }

.progress-sim-id {
  font-size: 10px;
  color: #999;
  margin-bottom: 8px;
}

.mono { font-family: 'JetBrains Mono', monospace; }

.progress-bar-container {
  background: #f0f0f0;
  border-radius: 4px;
  height: 24px;
  position: relative;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-bar {
  height: 100%;
  background: #ff5722;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.progress-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 10px;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
}

.progress-actions {
  display: flex;
  gap: 16px;
  font-size: 11px;
  color: #666;
  font-family: 'JetBrains Mono', monospace;
}

.progress-error {
  font-size: 11px;
  color: #c62828;
  margin-top: 4px;
}

.auto-config {
  display: flex;
  gap: 12px;
  margin-bottom: 10px;
}

.num-input {
  width: 60px;
  border: 1px solid #ddd;
  padding: 6px 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  border-radius: 4px;
  margin-left: 6px;
}

.auto-status {
  margin-top: 12px;
  border: 1px solid #eaeaea;
  border-radius: 6px;
  padding: 12px;
}

.auto-progress {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  margin-bottom: 8px;
}

.auto-status-badge {
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 3px;
  margin-left: 8px;
  background: #f0f0f0;
  color: #666;
}
.auto-status-badge.running { background: #fff3e0; color: #e65100; }
.auto-status-badge.completed { background: #e8f5e9; color: #2e7d32; }
.auto-status-badge.failed { background: #ffebee; color: #c62828; }

.auto-best {
  background: #e8f5e9;
  border: 1px solid #c8e6c9;
  border-radius: 4px;
  padding: 10px;
  margin-bottom: 10px;
  font-size: 13px;
}

.auto-reasoning {
  font-size: 11px;
  color: #555;
  margin-top: 4px;
}

.auto-iteration-card {
  border: 1px solid #eaeaea;
  border-radius: 4px;
  padding: 8px;
  margin-bottom: 6px;
}

.auto-iter-header {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 600;
  color: #999;
  margin-bottom: 6px;
}

.auto-branch-result {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  padding: 3px 0;
}

.auto-verdict {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 2px;
}
.auto-verdict.keep { background: #e8f5e9; color: #2e7d32; }
.auto-verdict.discard { background: #ffebee; color: #c62828; }

.auto-branch-label { font-weight: 500; flex: 1; }
.auto-branch-score {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #666;
}

.comparison-section {
  margin-bottom: 24px;
  border: 1px solid #eaeaea;
  border-radius: 6px;
  padding: 16px;
}

.comparison-grid {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.comparison-card {
  flex: 1;
  min-width: 200px;
  border: 1px solid #eaeaea;
  border-radius: 6px;
  padding: 12px;
}

.comparison-label {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #eaeaea;
}

.comparison-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 8px;
}

.comp-stat {
  text-align: center;
}

.comp-value {
  display: block;
  font-family: 'JetBrains Mono', monospace;
  font-size: 18px;
  font-weight: 700;
}

.comp-key {
  font-size: 9px;
  color: #999;
  text-transform: uppercase;
}

.comp-top-posters {
  font-size: 10px;
  color: #666;
}

.top-poster {
  font-family: 'JetBrains Mono', monospace;
  margin-left: 4px;
}

.consequence-btn {
  margin-top: 8px;
  width: 100%;
  background: #f5f5f5;
  color: #333;
  border: 1px solid #ddd;
  padding: 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
}
.consequence-btn:hover { background: #e0e0e0; }

.consequence-section {
  margin-top: 24px;
  border: 1px solid #eaeaea;
  border-radius: 6px;
  padding: 16px;
  min-height: 400px;
}

.branch-progress-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>
