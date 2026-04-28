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
              v-if="brief && !briefOpen"
              type="button"
              class="view-brief"
              @click="briefOpen = true"
            >View brief</button>
            <button
              type="button"
              class="launch"
              :disabled="!readyToLaunch || loading"
              @click="launch"
            >{{ brief ? 'Regenerate ▶' : 'Launch ▶' }}</button>
          </div>
        </form>
      </section>

      <SeedSlotsPanel :seed-state="seedState" />
    </main>

    <div v-if="briefOpen" class="brief-overlay" @click.self="briefOpen = false">
      <div class="brief-modal">
        <header class="brief-header">
          <h2>Research brief</h2>
          <button type="button" class="close" @click="briefOpen = false">×</button>
        </header>
        <div class="brief-body" v-html="renderedBrief"></div>
        <footer class="brief-footer">
          <button type="button" class="secondary" @click="copyBrief">Copy markdown</button>
          <button type="button" class="primary" @click="briefOpen = false">Close</button>
        </footer>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marked } from 'marked'
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

marked.setOptions({ gfm: true, breaks: false })

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

const brief = ref('')
const briefOpen = ref(false)

const renderedBrief = computed(() => brief.value ? marked.parse(brief.value) : '')

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
  brief.value = session.brief || ''
  briefOpen.value = false
}

function clearLocalState() {
  activeSessionId.value = null
  messages.value = [{ ...DEFAULT_GREETING }]
  Object.assign(seedState, emptySeed())
  readyToLaunch.value = false
  error.value = ''
  draft.value = ''
  brief.value = ''
  briefOpen.value = false
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
  if (!activeSessionId.value) {
    error.value = 'No active session — send a message first.'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const data = await postLaunch({ session_id: activeSessionId.value })
    if (!data?.brief_markdown) {
      error.value = 'Launch returned no brief.'
      return
    }
    brief.value = data.brief_markdown
    briefOpen.value = true
    await refreshSessions()
  } catch (err) {
    const status = err?.response?.status
    if (status === 400) {
      error.value = err?.response?.data?.error || 'Seed missing required slots.'
    } else if (status === 503) {
      error.value = 'Claude CLI not reachable on the server.'
    } else {
      error.value = err?.response?.data?.error || err.message
    }
  } finally {
    loading.value = false
  }
}

async function copyBrief() {
  try {
    await navigator.clipboard.writeText(brief.value)
  } catch {
    error.value = 'Copy failed — your browser blocked clipboard access.'
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
  justify-content: flex-end;
  gap: 0.5rem;
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
.actions button[type="submit"] { margin-right: auto; }
.actions .view-brief { background: #2a2a4a; color: #ddd; }
.actions .launch { background: #4ade80; color: #052e16; font-weight: bold; }
.actions .launch:disabled { background: #1a3a1a; color: #555; }

.brief-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.brief-modal {
  width: min(900px, 90vw);
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  background: #111;
  border: 1px solid #333;
  border-radius: 6px;
  overflow: hidden;
}
.brief-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid #222;
}
.brief-header h2 { margin: 0; font-size: 1rem; letter-spacing: 0.05em; }
.brief-header .close {
  background: transparent;
  color: #888;
  border: 0;
  font-size: 1.5rem;
  cursor: pointer;
  line-height: 1;
}
.brief-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem 1.5rem;
  line-height: 1.55;
}
.brief-body :deep(h1),
.brief-body :deep(h2),
.brief-body :deep(h3) { margin-top: 1.25em; }
.brief-body :deep(h1) { font-size: 1.4rem; }
.brief-body :deep(h2) { font-size: 1.15rem; color: #e5e5e5; border-bottom: 1px solid #222; padding-bottom: 0.25rem; }
.brief-body :deep(h3) { font-size: 1rem; color: #ddd; }
.brief-body :deep(p) { margin: 0.6em 0; }
.brief-body :deep(ul),
.brief-body :deep(ol) { padding-left: 1.5rem; }
.brief-body :deep(li) { margin: 0.25em 0; }
.brief-body :deep(strong) { color: #fff; }
.brief-body :deep(code) { background: #222; padding: 0 0.25em; border-radius: 3px; }
.brief-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 0.75rem 1.25rem;
  border-top: 1px solid #222;
}
.brief-footer button {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid #444;
  font-family: inherit;
}
.brief-footer .primary { background: #4ade80; color: #052e16; font-weight: bold; }
.brief-footer .secondary { background: #333; color: #ddd; }
</style>
