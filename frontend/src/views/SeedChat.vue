<template>
  <div class="seedchat-layout">
    <header class="topbar">
      <div class="brand">MIROSHARK</div>
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
import { ref, reactive, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import SeedSlotsPanel from '../components/SeedSlotsPanel.vue'
import { postTurn, postLaunch } from '../api/seedChat.js'

const router = useRouter()

const messages = ref([
  {
    role: 'assistant',
    content: "What would you like to investigate? Describe the question, decision, or debate you're trying to understand.",
  },
])

const seedState = reactive({
  topic: '',
  intent: '',
  stakeholders: [],
  decision_branches: [],
  contested_claims: [],
  output_format: '',
})

const readyToLaunch = ref(false)
const draft = ref('')
const loading = ref(false)
const error = ref('')
const messagesEl = ref(null)

async function sendMessage() {
  const text = draft.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  draft.value = ''
  loading.value = true
  error.value = ''

  try {
    // The axios interceptor in api/index.js unwraps response.data already,
    // so postTurn resolves to the parsed JSON body directly.
    const data = await postTurn({
      messages: messages.value,
      seed_state: seedState,
    })
    messages.value.push({ role: 'assistant', content: data.assistant_message })
    Object.assign(seedState, data.updated_seed_state)
    readyToLaunch.value = data.ready_to_launch
  } catch (err) {
    const status = err?.response?.status
    if (status === 503) {
      error.value = 'Claude CLI not reachable on the server. Check `claude --version`.'
    } else {
      error.value = err?.response?.data?.error || err.message
    }
  } finally {
    loading.value = false
    await nextTick()
    if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}

async function launch() {
  loading.value = true
  error.value = ''
  try {
    // The axios interceptor unwraps response.data already.
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
}
.brand { font-weight: bold; letter-spacing: 0.15em; }
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
