<template>
  <div class="tree-layout">
    <header class="topbar">
      <button class="back-btn" type="button" @click="goBack">← Back to chat</button>
      <div class="brand">DECISION TREE</div>
      <div class="topic">{{ tree?.question || 'Loading…' }}</div>
    </header>

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
      />
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TreeNode from '../components/TreeNode.vue'
import {
  getSession,
  postTreeInit,
  postTreeExpand,
  postTreeResearch,
  postTreeUpdateNode,
} from '../api/seedChat.js'

const route = useRoute()
const router = useRouter()

const sessionId = route.params.sessionId
const tree = ref(null)
const loading = ref(true)
const error = ref('')

// Per-node loading flags: { [nodeId]: { expand?: bool, research?: bool } }
const busyMap = reactive({})

function setBusy(nodeId, action, value) {
  if (!busyMap[nodeId]) busyMap[nodeId] = {}
  busyMap[nodeId][action] = value
}

function goBack() {
  router.push({ name: 'SeedChat', query: { session: sessionId } })
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
</style>
