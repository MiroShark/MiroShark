<template>
  <div class="seedchat-layout">
    <header class="topbar">
      <div class="brand">MIROSHARK</div>
      <div class="topbar-center">
        <SessionMenu
          :sessions="sessions"
          :active-id="activeSessionId"
          @select="onSelectSession"
          @new="onNewSession"
        />
      </div>
      <div class="links">
        <router-link to="/legacy" class="link">Upload mode <span class="arrow">↗</span></router-link>
        <router-link to="/decision-lab/new" class="link">Decision Lab <span class="arrow">↗</span></router-link>
      </div>
    </header>

    <main class="body">
      <section class="chat-pane">
        <div class="messages" ref="messagesEl">
          <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
            <div class="msg-content">{{ m.content }}</div>
          </div>
          <div v-if="loading" class="msg assistant loading">
            <div class="msg-content">…</div>
          </div>
          <div v-if="error" class="error">{{ error }}</div>
        </div>

        <form class="composer" @submit.prevent="sendMessage">
          <textarea
            v-model="draft"
            placeholder="Describe what you want to investigate…"
            rows="3"
            :disabled="loading"
            @keydown.enter.exact.prevent="sendMessage"
          ></textarea>
          <div class="actions">
            <button type="submit" :disabled="!draft.trim() || loading">Send</button>
            <button
              type="button"
              class="launch"
              :disabled="!readyToLaunch || loading"
              @click="launch"
            >Launch ▶</button>
          </div>
        </form>
      </section>

      <SeedSlotsPanel :seed-state="seedState" />
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SeedSlotsPanel from '../components/SeedSlotsPanel.vue'
import SessionMenu from '../components/SessionMenu.vue'
import {
  postTurn,
  postLaunch,
  listSessions,
  getSession,
  createSession,
} from '../api/seedChat.js'

const router = useRouter()
const route = useRoute()

const DEFAULT_GREETING = {
  role: 'assistant',
  content: "What would you like to investigate? Describe the question, decision, or debate you're trying to understand.",
}

function emptySeed() {
  return {
    topic: '',
    intent: '',
    stakeholders: [],
    decision_branches: [],
    contested_claims: [],
    output_format: '',
  }
}

const messages = ref([{ ...DEFAULT_GREETING }])
const seedState = reactive(emptySeed())
const readyToLaunch = ref(false)
const draft = ref('')
const loading = ref(false)
const error = ref('')
const messagesEl = ref(null)

const sessions = ref([])
const activeSessionId = ref(null)

async function refreshSessions() {
  try {
    const data = await listSessions()
    sessions.value = data?.sessions || []
  } catch (err) {
    console.warn('Failed to load sessions:', err)
  }
}

function applySession(session) {
  if (!session) return
  activeSessionId.value = session.id
  messages.value = session.messages?.length
    ? session.messages.map(m => ({ ...m }))
    : [{ ...DEFAULT_GREETING }]
  Object.assign(seedState, emptySeed(), session.seed_state || {})
  readyToLaunch.value = !!session.ready_to_launch
}

function clearLocalState() {
  activeSessionId.value = null
  messages.value = [{ ...DEFAULT_GREETING }]
  Object.assign(seedState, emptySeed())
  readyToLaunch.value = false
  error.value = ''
  draft.value = ''
}

function setUrlSession(id) {
  const query = id ? { session: id } : {}
  router.replace({ name: route.name, query }).catch(() => {})
}

async function onSelectSession(id) {
  if (id === activeSessionId.value) return
  loading.value = true
  error.value = ''
  try {
    const session = await getSession(id)
    applySession(session)
    setUrlSession(id)
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    loading.value = false
    await scrollMessagesToEnd()
  }
}

function onNewSession() {
  clearLocalState()
  setUrlSession(null)
}

async function ensureSession() {
  if (activeSessionId.value) return activeSessionId.value
  const session = await createSession()
  activeSessionId.value = session.id
  setUrlSession(session.id)
  return session.id
}

async function sendMessage() {
  const text = draft.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  draft.value = ''
  loading.value = true
  error.value = ''

  try {
    const sessionId = await ensureSession()
    const data = await postTurn({
      messages: messages.value,
      seed_state: seedState,
      session_id: sessionId,
    })
    messages.value.push({ role: 'assistant', content: data.assistant_message })
    Object.assign(seedState, data.updated_seed_state)
    readyToLaunch.value = data.ready_to_launch
    await refreshSessions()
  } catch (err) {
    const status = err?.response?.status
    if (status === 503) {
      error.value = 'Claude CLI not reachable on the server. Check `claude --version`.'
    } else {
      error.value = err?.response?.data?.error || err.message
    }
  } finally {
    loading.value = false
    await scrollMessagesToEnd()
  }
}

async function scrollMessagesToEnd() {
  await nextTick()
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
}

async function launch() {
  loading.value = true
  error.value = ''
  try {
    const data = await postLaunch({ seed: seedState })
    if (data?.redirect_url) {
      window.location.href = data.redirect_url
    } else if (data?.project_id) {
      router.push({ name: 'Process', params: { projectId: data.project_id } })
    } else {
      error.value = 'Launch returned no project id.'
    }
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await refreshSessions()
  const querySessionId = route.query?.session
  if (querySessionId) {
    try {
      const session = await getSession(querySessionId)
      if (session) applySession(session)
    } catch (err) {
      console.warn('Failed to load session from URL:', err)
    }
  }
})
</script>

<style scoped>
.seedchat-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0a0a0a;
  color: #ddd;
  font-family: system-ui, sans-serif;
}
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid #222;
  gap: 1rem;
}
.brand { font-weight: bold; letter-spacing: 0.15em; }
.topbar-center {
  flex: 1;
  display: flex;
  justify-content: center;
}
.links .link {
  color: #ddd;
  text-decoration: none;
  margin-left: 1rem;
  font-size: 0.85rem;
}
.body {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 360px;
  min-height: 0;
}
.chat-pane {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 1.5rem;
}
.msg {
  margin: 0.75rem 0;
  display: flex;
}
.msg.user { justify-content: flex-end; }
.msg-content {
  max-width: 70%;
  padding: 0.6rem 0.9rem;
  border-radius: 6px;
  white-space: pre-wrap;
}
.msg.user .msg-content { background: #1f3a5f; }
.msg.assistant .msg-content { background: #1a1a1a; }
.msg.loading .msg-content { opacity: 0.5; }
.error { color: #f87171; padding: 0.5rem; }
.composer {
  border-top: 1px solid #222;
  padding: 0.75rem 1.5rem;
}
.composer textarea {
  width: 100%;
  background: #111;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 4px;
  padding: 0.5rem;
  resize: vertical;
  font-family: inherit;
}
.actions {
  display: flex;
  justify-content: space-between;
  margin-top: 0.5rem;
}
.actions button {
  padding: 0.5rem 1rem;
  background: #333;
  color: #ddd;
  border: 1px solid #444;
  cursor: pointer;
  border-radius: 4px;
}
.actions button:disabled { opacity: 0.4; cursor: not-allowed; }
.actions .launch { background: #4ade80; color: #052e16; font-weight: bold; }
.actions .launch:disabled { background: #1a3a1a; color: #555; }
</style>
