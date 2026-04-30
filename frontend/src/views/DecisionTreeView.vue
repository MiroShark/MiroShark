<template>
  <div class="tree-layout">
    <header class="topbar">
      <button class="back-btn" type="button" @click="goBack">← Back to chat</button>
      <div class="brand">DECISION TREE</div>
      <div class="topic">{{ tree?.question || 'Loading…' }}</div>
      <button
        type="button"
        class="map-view-btn"
        :disabled="!tree"
        @click="goToMap"
      >Map view 🗺️</button>
      <button
        v-if="!researchingAll"
        type="button"
        class="research-all-btn"
        :disabled="!tree || synthesizingAll"
        @click="researchAll"
      >Research all 🔁</button>
      <button
        v-else
        type="button"
        class="stop-btn"
        @click="stopResearchAll"
      >Stop research</button>
      <button
        v-if="!synthesizingAll"
        type="button"
        class="synthesize-all-btn"
        :disabled="!tree || researchingAll"
        @click="synthesizeAll"
      >Synthesize all ✨</button>
      <button
        v-else
        type="button"
        class="stop-btn"
        @click="stopSynthesizeAll"
      >Stop synth</button>
      <button
        type="button"
        class="foresight-btn"
        :disabled="!tree || researchingAll || synthesizingAll || compilingForesight"
        @click="compileForesight"
      >{{ compilingForesight ? 'Compiling…' : (foresight ? 'View foresight 📄' : 'Compile foresight 📄') }}</button>
    </header>

    <div v-if="researchingAll" class="research-progress-banner" role="status" aria-live="polite">
      <span class="spinner-dot"></span>
      <span class="spinner-dot"></span>
      <span class="spinner-dot"></span>
      <span class="progress-text">
        Researching node {{ researchProgress.current }} of {{ researchProgress.total }}:
        <span class="progress-question">"{{ researchProgress.label }}"</span>
      </span>
    </div>

    <div v-if="synthesizingAll" class="research-progress-banner" role="status" aria-live="polite">
      <span class="spinner-dot"></span>
      <span class="spinner-dot"></span>
      <span class="spinner-dot"></span>
      <span class="progress-text">
        Synthesizing node {{ synthProgress.current }} of {{ synthProgress.total }}:
        <span class="progress-question">"{{ synthProgress.label }}"</span>
      </span>
    </div>

    <main class="tree-body">
      <div v-if="error" class="error">{{ error }}</div>
      <div v-if="loading && !tree" class="loading">Loading tree…</div>

      <TreeNode
        v-if="tree"
        :node="tree"
        :busy-map="busyMap"
        @expand="onExpand"
        @research="onResearch"
        @update-node="onUpdateNode"
        @synthesize="onSynthesize"
      />
    </main>

    <div v-if="foresightOpen" class="foresight-overlay" @click.self="foresightOpen = false">
      <div class="foresight-modal">
        <header class="foresight-header">
          <h2>Foresight document</h2>
          <button type="button" class="close" @click="foresightOpen = false">×</button>
        </header>
        <div class="foresight-body" v-html="renderedForesight"></div>
        <footer class="foresight-footer">
          <button type="button" class="secondary" @click="copyForesight">Copy markdown</button>
          <button type="button" class="secondary" @click="downloadForesight">Download .md</button>
          <button
            type="button"
            class="primary"
            :disabled="compilingForesight"
            @click="regenerateForesight"
          >{{ compilingForesight ? 'Regenerating…' : 'Regenerate' }}</button>
          <button type="button" class="secondary" @click="foresightOpen = false">Close</button>
        </footer>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TreeNode from '../components/TreeNode.vue'
import {
  getSession,
  postTreeInit,
  postTreeExpand,
  postTreeResearch,
  postTreeUpdateNode,
  postTreeSynthesize,
  postCompileForesight,
} from '../api/seedChat.js'
import { marked } from 'marked'

const route = useRoute()
const router = useRouter()

const sessionId = route.params.sessionId
const tree = ref(null)
const loading = ref(true)
const error = ref('')

// Per-node loading flags: { [nodeId]: { expand?: bool, research?: bool } }
const busyMap = reactive({})

const researchingAll = ref(false)
const stopRequested = ref(false)
const researchProgress = ref({ current: 0, total: 0, label: '' })

const synthesizingAll = ref(false)
const synthStopRequested = ref(false)
const synthProgress = ref({ current: 0, total: 0, label: '' })

const foresight = ref('')
const foresightOpen = ref(false)
const compilingForesight = ref(false)

const renderedForesight = computed(() =>
  foresight.value ? marked.parse(foresight.value) : ''
)

function setBusy(nodeId, action, value) {
  if (!busyMap[nodeId]) busyMap[nodeId] = {}
  busyMap[nodeId][action] = value
}

function flattenBfs(root) {
  const out = []
  const queue = [root]
  while (queue.length > 0) {
    const node = queue.shift()
    out.push(node)
    for (const child of node.children || []) {
      queue.push(child)
    }
  }
  return out
}

function goBack() {
  router.push({ name: 'SeedChat', query: { session: sessionId } })
}

function goToMap() {
  router.push({ name: 'DecisionTreeMap', params: { sessionId } })
}

async function loadTree() {
  loading.value = true
  error.value = ''
  try {
    const session = await getSession(sessionId)
    if (session?.tree) {
      tree.value = session.tree
    } else {
      const data = await postTreeInit({ session_id: sessionId })
      tree.value = data.tree
    }
    if (session?.foresight) {
      foresight.value = session.foresight
    }
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    loading.value = false
  }
}

async function onExpand(nodeId) {
  setBusy(nodeId, 'expand', true)
  error.value = ''
  try {
    const data = await postTreeExpand({ session_id: sessionId, node_id: nodeId })
    if (data?.tree) tree.value = data.tree
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    setBusy(nodeId, 'expand', false)
  }
}

async function onResearch(nodeId) {
  setBusy(nodeId, 'research', true)
  error.value = ''
  try {
    await postTreeResearch({ session_id: sessionId, node_id: nodeId })
    // Re-fetch the session to get the updated tree (research returns evidence
    // for the node only, not the whole tree).
    const session = await getSession(sessionId)
    if (session?.tree) tree.value = session.tree
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    setBusy(nodeId, 'research', false)
  }
}

async function researchAll() {
  if (!tree.value || researchingAll.value) return

  const nodes = flattenBfs(tree.value).filter(n => !(n.evidence?.length > 0))

  if (nodes.length === 0) {
    error.value = 'All nodes already have evidence. Click Research on a single node to refresh.'
    return
  }

  researchingAll.value = true
  stopRequested.value = false
  error.value = ''
  researchProgress.value = { current: 0, total: nodes.length, label: '' }

  for (let i = 0; i < nodes.length; i++) {
    if (stopRequested.value) break

    const node = nodes[i]
    researchProgress.value = {
      current: i + 1,
      total: nodes.length,
      label: node.question,
    }

    setBusy(node.id, 'research', true)
    try {
      await postTreeResearch({ session_id: sessionId, node_id: node.id })
      const session = await getSession(sessionId)
      if (session?.tree) tree.value = session.tree
    } catch (err) {
      const msg = err?.response?.data?.error || err.message
      error.value = `Node ${i + 1} failed: ${msg}. Continuing.`
    } finally {
      setBusy(node.id, 'research', false)
    }
  }

  researchingAll.value = false
  researchProgress.value = { current: 0, total: 0, label: '' }
}

function stopResearchAll() {
  stopRequested.value = true
}

async function onSynthesize(nodeId) {
  setBusy(nodeId, 'synthesize', true)
  error.value = ''
  try {
    await postTreeSynthesize({ session_id: sessionId, node_id: nodeId })
    const session = await getSession(sessionId)
    if (session?.tree) tree.value = session.tree
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    setBusy(nodeId, 'synthesize', false)
  }
}

async function synthesizeAll() {
  if (!tree.value || synthesizingAll.value) return
  const nodes = flattenBfs(tree.value).filter(
    n => (n.evidence?.length > 0) && !n.summary
  )
  if (nodes.length === 0) {
    error.value = 'Nothing to synthesize. Run Research first or all nodes already summarized.'
    return
  }
  synthesizingAll.value = true
  synthStopRequested.value = false
  error.value = ''
  synthProgress.value = { current: 0, total: nodes.length, label: '' }
  for (let i = 0; i < nodes.length; i++) {
    if (synthStopRequested.value) break
    const node = nodes[i]
    synthProgress.value = {
      current: i + 1,
      total: nodes.length,
      label: node.question,
    }
    setBusy(node.id, 'synthesize', true)
    try {
      await postTreeSynthesize({ session_id: sessionId, node_id: node.id })
      const session = await getSession(sessionId)
      if (session?.tree) tree.value = session.tree
    } catch (err) {
      const msg = err?.response?.data?.error || err.message
      error.value = `Node ${i + 1} failed: ${msg}. Continuing.`
    } finally {
      setBusy(node.id, 'synthesize', false)
    }
  }
  synthesizingAll.value = false
  synthProgress.value = { current: 0, total: 0, label: '' }
}

function stopSynthesizeAll() {
  synthStopRequested.value = true
}

async function compileForesight() {
  if (!tree.value || compilingForesight.value) return
  // If we already have a foresight doc, just open the modal
  if (foresight.value && !foresightOpen.value) {
    foresightOpen.value = true
    return
  }
  compilingForesight.value = true
  error.value = ''
  try {
    const data = await postCompileForesight({ session_id: sessionId })
    if (data?.foresight) {
      foresight.value = data.foresight
      foresightOpen.value = true
    }
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    compilingForesight.value = false
  }
}

async function regenerateForesight() {
  // Force recompile even if foresight exists
  if (compilingForesight.value) return
  compilingForesight.value = true
  error.value = ''
  try {
    const data = await postCompileForesight({ session_id: sessionId })
    if (data?.foresight) {
      foresight.value = data.foresight
    }
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    compilingForesight.value = false
  }
}

async function copyForesight() {
  try {
    await navigator.clipboard.writeText(foresight.value)
  } catch {
    error.value = 'Copy failed — your browser blocked clipboard access.'
  }
}

function downloadForesight() {
  if (!foresight.value) return
  const date = new Date().toISOString().slice(0, 10)
  const slug = (tree.value?.question || 'foresight')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60) || 'foresight'
  const blob = new Blob([foresight.value], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `foresight-${slug}-${date}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

async function onUpdateNode({ node_id, fields }) {
  try {
    const data = await postTreeUpdateNode({
      session_id: sessionId,
      node_id,
      fields,
    })
    if (data?.tree) tree.value = data.tree
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  }
}

onMounted(loadTree)
</script>

<style scoped>
.tree-layout {
  min-height: 100vh;
  background: #0a0a0a;
  color: #ddd;
  font-family: system-ui, sans-serif;
  display: flex;
  flex-direction: column;
}
.topbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid #222;
}
.back-btn {
  background: transparent;
  border: 1px solid #333;
  color: #ddd;
  padding: 0.35rem 0.7rem;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.85rem;
}
.back-btn:hover { background: #1a1a1a; }
.brand { font-weight: bold; letter-spacing: 0.15em; }
.topic { color: #aaa; font-size: 0.9rem; flex: 1; }
.tree-body {
  flex: 1;
  padding: 1.25rem;
  max-width: 1100px;
  width: 100%;
  margin: 0 auto;
}
.error { color: #f87171; padding: 0.5rem; margin-bottom: 0.5rem; }
.loading { color: #aaa; font-style: italic; }

.research-all-btn,
.stop-btn {
  background: #2a4a2a;
  color: #d6f5d6;
  border: 1px solid #3a6a3a;
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 500;
}
.research-all-btn:hover { background: #335933; }
.research-all-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.stop-btn {
  background: #4a2a2a;
  color: #f5d6d6;
  border-color: #6a3a3a;
}
.stop-btn:hover { background: #593333; }

.research-progress-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 1.25rem;
  background: #1a2a3a;
  border-bottom: 1px solid #2a4a6a;
  color: #b8d6f5;
  font-size: 0.85rem;
}
.research-progress-banner .spinner-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #80b4ff;
  animation: progressPulse 1.4s infinite ease-in-out both;
}
.research-progress-banner .spinner-dot:nth-child(1) { animation-delay: -0.32s; }
.research-progress-banner .spinner-dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes progressPulse {
  0%, 80%, 100% { opacity: 0.2; }
  40% { opacity: 1; }
}
.progress-text { margin-left: 0.5rem; }
.progress-question {
  font-style: italic;
  color: #aaa;
  margin-left: 0.25rem;
}
.synthesize-all-btn {
  background: #2a2a4a;
  color: #d6d6f5;
  border: 1px solid #3a3a6a;
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 500;
  margin-left: 0.5rem;
}
.synthesize-all-btn:hover { background: #353559; }
.synthesize-all-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.foresight-btn {
  background: #4a3a2a;
  color: #f5e8d6;
  border: 1px solid #6a5a3a;
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 500;
  margin-left: 0.5rem;
}
.foresight-btn:hover { background: #5a4a35; }
.foresight-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.foresight-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.foresight-modal {
  width: min(900px, 90vw);
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  background: #111;
  border: 1px solid #333;
  border-radius: 6px;
  overflow: hidden;
}
.foresight-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid #222;
}
.foresight-header h2 { margin: 0; font-size: 1rem; letter-spacing: 0.05em; }
.foresight-header .close {
  background: transparent;
  color: #888;
  border: 0;
  font-size: 1.5rem;
  cursor: pointer;
  line-height: 1;
}
.foresight-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem 1.5rem;
  line-height: 1.55;
}
.foresight-body :deep(h1),
.foresight-body :deep(h2),
.foresight-body :deep(h3) { margin-top: 1.25em; }
.foresight-body :deep(h1) { font-size: 1.4rem; color: #f5e8d6; }
.foresight-body :deep(h2) {
  font-size: 1.15rem;
  color: #e5e5e5;
  border-bottom: 1px solid #222;
  padding-bottom: 0.25rem;
}
.foresight-body :deep(h3) { font-size: 1rem; color: #ddd; }
.foresight-body :deep(p) { margin: 0.6em 0; }
.foresight-body :deep(ul),
.foresight-body :deep(ol) { padding-left: 1.5rem; }
.foresight-body :deep(li) { margin: 0.25em 0; }
.foresight-body :deep(strong) { color: #fff; }
.foresight-body :deep(a) { color: #80b4ff; }

.foresight-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 0.75rem 1.25rem;
  border-top: 1px solid #222;
}
.foresight-footer button {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid #444;
  font-family: inherit;
}
.foresight-footer .primary { background: #4ade80; color: #052e16; font-weight: bold; }
.foresight-footer .secondary { background: #333; color: #ddd; }
.foresight-footer button:disabled { opacity: 0.5; cursor: not-allowed; }

.map-view-btn {
  background: #4a3a2a;
  color: #f5e8d6;
  border: 1px solid #6a5a3a;
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 500;
  margin-left: 0.5rem;
}
.map-view-btn:hover { background: #5a4a35; }
.map-view-btn:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
