<template>
  <Teleport to="body">
    <div v-if="open" class="settings-overlay" @click.self="$emit('close')">
      <div class="settings-modal">
        <!-- Header -->
        <div class="modal-header">
          <div class="modal-title">
            <span class="title-label">⚙ Settings</span>
          </div>
          <button class="close-btn" @click="$emit('close')">✕</button>
        </div>

        <div class="warning-stripe"></div>

        <!-- Current Setup Summary -->
        <section class="settings-section">
          <div class="section-header">
            <span class="section-label">Current Setup</span>
            <div class="status-badge" :class="testStatus">
              <span class="badge-dot"></span>
              {{ testStatusText }}
            </div>
          </div>

          <div class="setup-grid">
            <div class="setup-row">
              <span class="setup-key">Default model</span>
              <span class="setup-val">{{ currentSettings.llm?.model_name || '—' }}</span>
            </div>
            <div class="setup-row">
              <span class="setup-key">Smart (reports)</span>
              <span class="setup-val">{{ currentSettings.smart?.model_name || inheritMarker }}</span>
            </div>
            <div class="setup-row">
              <span class="setup-key">NER (extraction)</span>
              <span class="setup-val">{{ currentSettings.ner?.model_name || inheritMarker }}</span>
            </div>
            <div class="setup-row">
              <span class="setup-key">Wonderwall (sim loop)</span>
              <span class="setup-val">{{ currentSettings.wonderwall?.model_name || inheritMarker }}</span>
            </div>
            <div class="setup-row">
              <span class="setup-key">Embeddings</span>
              <span class="setup-val">
                {{ currentSettings.embedding?.model_name || '—' }}
              </span>
            </div>
            <div class="setup-row">
              <span class="setup-key">Web search</span>
              <span class="setup-val">{{ currentSettings.web_search_model || inheritMarker }}</span>
            </div>
            <div class="setup-row">
              <span class="setup-key">API key</span>
              <span class="setup-val">
                <span v-if="currentSettings.llm?.has_api_key">
                  {{ currentSettings.llm.api_key_masked }}
                </span>
                <span v-else class="setup-missing">not set</span>
              </span>
            </div>
          </div>
        </section>

        <!-- Preset Picker -->
        <section class="settings-section">
          <div class="section-header">
            <span class="section-label">Preset</span>
          </div>

          <div class="field-row">
            <label class="field-label">Config template</label>
            <div class="select-wrapper">
              <select v-model="form.preset" class="field-select">
                <option value="">Custom — leave fields as they are</option>
                <option
                  v-for="p in presetOptions"
                  :key="p.id"
                  :value="p.id"
                >{{ p.label }}</option>
              </select>
            </div>
            <div class="field-hint">
              Applies the full set of model slots on save. See
              <a href="https://github.com/aaronjmars/MiroShark/blob/main/.env.example"
                 target="_blank" rel="noopener">.env.example</a>
              for the exact values each preset uses.
            </div>
          </div>

          <div v-if="presetNeedsKey" class="field-row">
            <label class="field-label">OpenRouter API key</label>
            <div class="key-input-group">
              <input
                v-model="form.presetApiKey"
                class="field-input"
                :type="showKey ? 'text' : 'password'"
                placeholder="sk-or-v1-..."
              />
              <button class="toggle-key-btn" @click="showKey = !showKey">
                {{ showKey ? '◉' : '◎' }}
              </button>
            </div>
            <div class="field-hint">
              Filled into every slot the preset needs (default, smart, NER, embedding).
              Leave blank to keep your existing keys.
            </div>
          </div>
        </section>

        <!-- LLM Configuration -->
        <section class="settings-section">
          <div class="section-header">
            <span class="section-label">LLM Configuration</span>
          </div>

          <!-- Provider -->
          <div class="field-row">
            <label class="field-label">Provider</label>
            <div class="select-wrapper">
              <select v-model="form.llm.provider" class="field-select">
                <option value="openai">OpenAI-compatible (OpenRouter, Ollama, etc.)</option>
                <option value="claude-code">Claude Code (local CLI)</option>
              </select>
            </div>
          </div>

          <!-- Base URL -->
          <div v-if="form.llm.provider !== 'claude-code'" class="field-row">
            <label class="field-label">Base URL</label>
            <input
              v-model="form.llm.base_url"
              class="field-input"
              type="url"
              placeholder="https://openrouter.ai/api/v1"
            />
          </div>

          <!-- Model -->
          <div v-if="form.llm.provider !== 'claude-code'" class="field-row">
            <label class="field-label">Model</label>
            <div class="model-input-group">
              <div class="select-wrapper model-select-wrapper">
                <select
                  v-if="modelList.length > 0"
                  v-model="form.llm.model_name"
                  class="field-select"
                >
                  <optgroup
                    v-for="tier in modelTiers"
                    :key="tier.label"
                    :label="tier.label"
                  >
                    <option
                      v-for="m in tier.models"
                      :key="m.id"
                      :value="m.id"
                    >{{ m.name }}</option>
                  </optgroup>
                </select>
                <input
                  v-else
                  v-model="form.llm.model_name"
                  class="field-input"
                  type="text"
                  placeholder="e.g. openai/gpt-4o-mini"
                />
              </div>
              <button
                class="load-models-btn"
                :disabled="loadingModels || !isOpenRouter"
                @click="loadOpenRouterModels"
                :title="isOpenRouter ? 'Load available models from OpenRouter' : 'Only available for OpenRouter base URL'"
              >
                <span v-if="loadingModels">...</span>
                <span v-else>↻</span>
              </button>
            </div>
            <div v-if="modelLoadError" class="field-error">{{ modelLoadError }}</div>
          </div>

          <!-- API Key -->
          <div v-if="form.llm.provider !== 'claude-code'" class="field-row">
            <label class="field-label">API Key</label>
            <div class="key-input-group">
              <input
                v-model="form.llm.api_key"
                class="field-input"
                :type="showKey ? 'text' : 'password'"
                :placeholder="currentSettings.llm?.api_key_masked || 'sk-...'"
              />
              <button class="toggle-key-btn" @click="showKey = !showKey">
                {{ showKey ? '◉' : '◎' }}
              </button>
            </div>
            <div v-if="currentSettings.llm?.has_api_key && !form.llm.api_key" class="field-hint">
              Current key: {{ currentSettings.llm.api_key_masked }} — leave blank to keep unchanged
            </div>
          </div>

          <!-- Test Connection -->
          <div v-if="form.llm.provider !== 'claude-code'" class="field-row test-row">
            <button
              class="test-btn"
              :disabled="testing"
              @click="testConnection"
            >
              <span v-if="testing">Testing...</span>
              <span v-else>Test Connection</span>
            </button>
            <div v-if="testResult" class="test-result" :class="testResult.success ? 'ok' : 'fail'">
              <span v-if="testResult.success">
                ✓ {{ testResult.model }} — {{ testResult.latency_ms }}ms
              </span>
              <span v-else>✗ {{ testResult.error }}</span>
            </div>
          </div>
        </section>

        <!-- Advanced: per-slot overrides -->
        <section class="settings-section">
          <button class="advanced-toggle" @click="advancedOpen = !advancedOpen">
            <span class="section-label">
              Advanced slot overrides
            </span>
            <span class="chevron">{{ advancedOpen ? '−' : '+' }}</span>
          </button>

          <div v-if="advancedOpen" class="advanced-body">
            <div class="advanced-hint">
              Each slot falls back to the default LLM config when left empty.
            </div>

            <!-- Smart -->
            <div class="advanced-group">
              <div class="advanced-group-title">Smart — report generation</div>
              <div class="field-row">
                <label class="field-label">Model</label>
                <input
                  v-model="form.smart.model_name"
                  class="field-input"
                  type="text"
                  placeholder="e.g. anthropic/claude-sonnet-4.6"
                />
              </div>
            </div>

            <!-- NER -->
            <div class="advanced-group">
              <div class="advanced-group-title">NER — entity extraction</div>
              <div class="field-row">
                <label class="field-label">Model</label>
                <input
                  v-model="form.ner.model_name"
                  class="field-input"
                  type="text"
                  placeholder="e.g. google/gemini-2.0-flash-001"
                />
              </div>
            </div>

            <!-- Wonderwall -->
            <div class="advanced-group">
              <div class="advanced-group-title">Wonderwall — simulation loop</div>
              <div class="field-row">
                <label class="field-label">Model</label>
                <input
                  v-model="form.wonderwall.model_name"
                  class="field-input"
                  type="text"
                  placeholder="e.g. google/gemini-2.0-flash-lite-001"
                />
              </div>
            </div>

            <!-- Embedding -->
            <div class="advanced-group">
              <div class="advanced-group-title">Embeddings</div>
              <div class="field-row">
                <label class="field-label">Provider</label>
                <div class="select-wrapper">
                  <select v-model="form.embedding.provider" class="field-select">
                    <option value="ollama">Ollama (local)</option>
                    <option value="openai">OpenAI-compatible</option>
                  </select>
                </div>
              </div>
              <div class="field-row">
                <label class="field-label">Model</label>
                <input
                  v-model="form.embedding.model_name"
                  class="field-input"
                  type="text"
                  placeholder="e.g. openai/text-embedding-3-small"
                />
              </div>
            </div>

            <!-- Web Search -->
            <div class="advanced-group">
              <div class="advanced-group-title">Web search (URL import + enrichment)</div>
              <div class="field-row">
                <label class="field-label">Model</label>
                <input
                  v-model="form.web_search_model"
                  class="field-input"
                  type="text"
                  placeholder="e.g. google/gemini-2.0-flash-001:online"
                />
              </div>
            </div>
          </div>
        </section>

        <!-- Neo4j Configuration -->
        <section class="settings-section">
          <div class="section-header">
            <span class="section-label">Graph Database (Neo4j)</span>
          </div>

          <div class="field-row">
            <label class="field-label">URI</label>
            <input
              v-model="form.neo4j.uri"
              class="field-input"
              type="text"
              placeholder="bolt://localhost:7687"
            />
          </div>

          <div class="field-row">
            <label class="field-label">User</label>
            <input
              v-model="form.neo4j.user"
              class="field-input"
              type="text"
              placeholder="neo4j"
            />
          </div>

          <div class="field-row">
            <label class="field-label">Password</label>
            <input
              v-model="form.neo4j.password"
              class="field-input"
              type="password"
              placeholder="Leave blank to keep unchanged"
            />
          </div>
        </section>

        <!-- AI Integration (MCP) -->
        <section class="settings-section ai-section">
          <div class="section-header">
            <span class="section-label">AI Integration · MCP</span>
            <div class="status-badge" :class="mcpHealthClass">
              <span class="badge-dot"></span>
              {{ mcpHealthText }}
            </div>
          </div>

          <div class="ai-intro">
            Wire MiroShark's knowledge graph into Claude Desktop, Cursor, Windsurf,
            or Continue. Pick your client, paste the snippet, restart the editor.
          </div>

          <div v-if="mcpLoading" class="ai-loading">Loading MCP catalog…</div>
          <div v-else-if="mcpLoadError" class="ai-error">
            {{ mcpLoadError }}
            <button class="ai-retry" @click="loadMcpStatus">Retry</button>
          </div>

          <div v-else-if="mcpStatus" class="ai-body">
            <!-- Health summary grid -->
            <div class="ai-summary">
              <div class="ai-summary-row">
                <span class="ai-summary-key">Server file</span>
                <span class="ai-summary-val" :class="mcpStatus.paths.mcp_script_exists ? '' : 'setup-missing'">
                  {{ mcpStatus.paths.mcp_script_exists ? 'present' : 'missing' }}
                </span>
              </div>
              <div class="ai-summary-row">
                <span class="ai-summary-key">Tools exposed</span>
                <span class="ai-summary-val">{{ mcpStatus.tool_count }}</span>
              </div>
              <div class="ai-summary-row">
                <span class="ai-summary-key">Neo4j</span>
                <span class="ai-summary-val" :class="mcpStatus.neo4j.connected ? '' : 'setup-missing'">
                  {{ mcpStatus.neo4j.connected ? 'connected' : 'unreachable' }}
                </span>
              </div>
              <div class="ai-summary-row" v-if="mcpStatus.neo4j.connected">
                <span class="ai-summary-key">Graphs available</span>
                <span class="ai-summary-val">
                  {{ mcpStatus.neo4j.graph_count ?? 0 }}
                  <span class="setup-aux" v-if="mcpStatus.neo4j.entity_count != null">
                    ({{ mcpStatus.neo4j.entity_count }} entities)
                  </span>
                </span>
              </div>
              <div class="ai-summary-row" v-if="mcpStatus.neo4j.error">
                <span class="ai-summary-key">Error</span>
                <span class="ai-summary-val ai-error-text">{{ mcpStatus.neo4j.error }}</span>
              </div>
            </div>

            <!-- Client tabs -->
            <div class="ai-tabs" role="tablist">
              <button
                v-for="key in clientOrder"
                :key="key"
                class="ai-tab"
                :class="{ active: activeClient === key }"
                role="tab"
                :aria-selected="activeClient === key"
                @click="activeClient = key"
              >
                {{ mcpStatus.clients[key]?.label || key }}
              </button>
            </div>

            <!-- Active client snippet -->
            <div v-if="currentClient" class="ai-client">
              <div class="ai-client-file">
                <span class="ai-client-file-label">Config file:</span>
                <code class="ai-client-file-path">{{ currentClient.file }}</code>
              </div>
              <div class="ai-snippet-wrap">
                <pre class="ai-snippet"><code>{{ formatJson(currentClient.config) }}</code></pre>
                <button
                  class="ai-copy-btn"
                  :class="{ ok: copyState === 'ok', fail: copyState === 'fail' }"
                  @click="copySnippet"
                >
                  {{ copyButtonLabel }}
                </button>
              </div>
              <div v-if="currentClient.notes" class="ai-client-notes">
                {{ currentClient.notes }}
              </div>
            </div>

            <!-- Tool catalog (collapsed by default) -->
            <button class="ai-tools-toggle" @click="toolsOpen = !toolsOpen">
              <span>{{ toolsOpen ? '▾' : '▸' }} {{ mcpStatus.tool_count }} tools available</span>
            </button>
            <ul v-if="toolsOpen" class="ai-tools-list">
              <li v-for="t in mcpStatus.tools" :key="t.name" class="ai-tool">
                <code class="ai-tool-name">{{ t.name }}</code>
                <span class="ai-tool-desc">{{ t.description }}</span>
              </li>
            </ul>

            <div class="ai-docs-link">
              Need a deeper walkthrough?
              <a :href="mcpStatus.docs_url" target="_blank" rel="noopener">Read the full MCP guide →</a>
            </div>
          </div>
        </section>

        <!-- Footer -->
        <div class="modal-footer">
          <div v-if="saveError" class="save-error">{{ saveError }}</div>
          <div v-if="saveSuccess" class="save-success">✓ Settings saved (runtime — edit .env to persist across restarts)</div>
          <div class="footer-actions">
            <button class="cancel-btn" @click="$emit('close')">Cancel</button>
            <button class="save-btn" :disabled="saving" @click="saveSettings">
              <span v-if="saving">Saving...</span>
              <span v-else>Save Settings →</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { getSettings, updateSettings, testLlmConnection } from '../api/settings'
import { getMcpStatus } from '../api/mcp'

const props = defineProps({
  open: { type: Boolean, required: true }
})

const emit = defineEmits(['close'])

// Current settings loaded from backend
const currentSettings = ref({})

// Form state
const form = reactive({
  preset: '',
  presetApiKey: '',
  llm: {
    provider: 'openai',
    base_url: '',
    model_name: '',
    api_key: '',
  },
  smart: { model_name: '' },
  ner: { model_name: '' },
  wonderwall: { model_name: '' },
  embedding: { provider: 'ollama', model_name: '' },
  web_search_model: '',
  neo4j: {
    uri: '',
    user: '',
    password: '',
  },
})

// UI state
const showKey = ref(false)
const saving = ref(false)
const saveError = ref('')
const saveSuccess = ref(false)
const testing = ref(false)
const testResult = ref(null)
const modelList = ref([])
const loadingModels = ref(false)
const modelLoadError = ref('')
const advancedOpen = ref(false)
const inheritMarker = '— inherits default —'

// MCP / AI Integration state
const mcpStatus = ref(null)
const mcpLoading = ref(false)
const mcpLoadError = ref('')
const clientOrder = ['claude_desktop', 'cursor', 'windsurf', 'continue', 'fallback_direct']
const activeClient = ref('claude_desktop')
const toolsOpen = ref(false)
const copyState = ref('') // '' | 'ok' | 'fail'

// Load current settings when panel opens
watch(() => props.open, async (isOpen) => {
  if (isOpen) {
    saveError.value = ''
    saveSuccess.value = false
    testResult.value = null
    form.preset = ''
    form.presetApiKey = ''
    copyState.value = ''
    await Promise.all([loadCurrentSettings(), loadMcpStatus()])
  }
})

const loadCurrentSettings = async () => {
  try {
    // Axios response interceptor already unwraps to the body, so `res`
    // is `{ success, data }` — not the raw axios response.
    const res = await getSettings()
    if (res?.success && res.data) {
      const d = res.data
      currentSettings.value = d
      form.llm.provider = d.llm.provider || 'openai'
      form.llm.base_url = d.llm.base_url || ''
      form.llm.model_name = d.llm.model_name || ''
      form.llm.api_key = '' // never pre-fill
      form.smart.model_name = d.smart?.model_name || ''
      form.ner.model_name = d.ner?.model_name || ''
      form.wonderwall.model_name = d.wonderwall?.model_name || ''
      form.embedding.provider = d.embedding?.provider || 'ollama'
      form.embedding.model_name = d.embedding?.model_name || ''
      form.web_search_model = d.web_search_model || ''
      form.neo4j.uri = d.neo4j?.uri || ''
      form.neo4j.user = d.neo4j?.user || ''
      form.neo4j.password = ''
    }
  } catch (_) {
    // Non-fatal
  }
}

const presetOptions = computed(() => currentSettings.value.available_presets || [])

// `local` preset doesn't need an API key — the others do.
const presetNeedsKey = computed(() =>
  form.preset === 'cheap' || form.preset === 'best'
)

// Whether current base URL is OpenRouter
const isOpenRouter = computed(() =>
  form.llm.base_url.includes('openrouter.ai')
)

// Model tiering thresholds (cost per 1M tokens, prompt side)
const MODEL_TIERS = [
  { label: 'Fast (< $0.50/M)', max: 0.5 },
  { label: 'Standard ($0.50–$5/M)', max: 5 },
  { label: 'Capable (> $5/M)', max: Infinity },
]

const modelTiers = computed(() => {
  if (modelList.value.length === 0) return []
  return MODEL_TIERS.map(tier => ({
    label: tier.label,
    models: modelList.value.filter(m => {
      const price = m.pricing?.prompt ? parseFloat(m.pricing.prompt) * 1_000_000 : 0
      return price <= tier.max && price > (tier === MODEL_TIERS[0] ? 0 : MODEL_TIERS[MODEL_TIERS.indexOf(tier) - 1].max)
    })
  })).filter(t => t.models.length > 0)
})

const loadOpenRouterModels = async () => {
  loadingModels.value = true
  modelLoadError.value = ''
  try {
    const res = await fetch('https://openrouter.ai/api/v1/models')
    const json = await res.json()
    if (json.data) {
      modelList.value = json.data
        .filter(m => m.id && m.name)
        .sort((a, b) => {
          const pa = parseFloat(a.pricing?.prompt || 0) * 1_000_000
          const pb = parseFloat(b.pricing?.prompt || 0) * 1_000_000
          return pa - pb
        })
    }
  } catch (_) {
    modelLoadError.value = 'Could not load model list — check your network connection.'
  } finally {
    loadingModels.value = false
  }
}

const testConnection = async () => {
  testing.value = true
  testResult.value = null
  try {
    // Interceptor unwraps axios to the body directly.
    const res = await testLlmConnection()
    testResult.value = res
  } catch (e) {
    testResult.value = { success: false, error: e.message }
  } finally {
    testing.value = false
  }
}

const loadMcpStatus = async () => {
  mcpLoading.value = true
  mcpLoadError.value = ''
  try {
    // Axios interceptor unwraps to { success, data }.
    const res = await getMcpStatus()
    if (res?.success && res.data) {
      mcpStatus.value = res.data
    } else {
      mcpLoadError.value = res?.error || 'MCP status unavailable'
    }
  } catch (e) {
    mcpLoadError.value = e?.message || 'MCP status request failed'
  } finally {
    mcpLoading.value = false
  }
}

const currentClient = computed(() => {
  if (!mcpStatus.value) return null
  return mcpStatus.value.clients?.[activeClient.value] || null
})

const mcpHealthClass = computed(() => {
  if (!mcpStatus.value) return 'idle'
  if (!mcpStatus.value.paths.mcp_script_exists) return 'fail'
  return mcpStatus.value.neo4j.connected ? 'ok' : 'fail'
})

const mcpHealthText = computed(() => {
  if (!mcpStatus.value) return 'Loading'
  if (!mcpStatus.value.paths.mcp_script_exists) return 'Server file missing'
  return mcpStatus.value.neo4j.connected ? 'Ready' : 'Neo4j down'
})

const formatJson = (obj) => JSON.stringify(obj, null, 2)

const copyButtonLabel = computed(() => {
  if (copyState.value === 'ok') return '✓ Copied'
  if (copyState.value === 'fail') return '✗ Copy failed'
  return 'Copy snippet'
})

const copySnippet = async () => {
  if (!currentClient.value) return
  const text = formatJson(currentClient.value.config)
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      // Fallback for older / non-secure-context browsers.
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      const ok = document.execCommand('copy')
      document.body.removeChild(ta)
      if (!ok) throw new Error('execCommand copy returned false')
    }
    copyState.value = 'ok'
  } catch (_) {
    copyState.value = 'fail'
  } finally {
    setTimeout(() => { copyState.value = '' }, 2200)
  }
}

const testStatus = computed(() => {
  if (!testResult.value) return 'idle'
  return testResult.value.success ? 'ok' : 'fail'
})

const testStatusText = computed(() => {
  if (!testResult.value) return 'Not tested'
  return testResult.value.success ? 'Connected' : 'Failed'
})

const saveSettings = async () => {
  saving.value = true
  saveError.value = ''
  saveSuccess.value = false
  try {
    const payload = {}

    // Preset is applied server-side first; explicit field overrides apply on top.
    if (form.preset) {
      payload.preset = form.preset
      if (form.presetApiKey) payload.preset_api_key = form.presetApiKey
    }

    payload.llm = {
      provider: form.llm.provider,
      base_url: form.llm.base_url,
      model_name: form.llm.model_name,
    }
    if (form.llm.api_key) payload.llm.api_key = form.llm.api_key

    payload.smart = { model_name: form.smart.model_name }
    payload.ner = { model_name: form.ner.model_name }
    payload.wonderwall = { model_name: form.wonderwall.model_name }
    payload.embedding = {
      provider: form.embedding.provider,
      model_name: form.embedding.model_name,
    }
    payload.web_search_model = form.web_search_model

    payload.neo4j = {
      uri: form.neo4j.uri,
      user: form.neo4j.user,
    }
    if (form.neo4j.password) payload.neo4j.password = form.neo4j.password

    const res = await updateSettings(payload)
    if (res?.success && res.data) {
      saveSuccess.value = true
      currentSettings.value = res.data
      form.llm.api_key = ''
      form.presetApiKey = ''
      form.neo4j.password = ''
      setTimeout(() => { saveSuccess.value = false }, 4000)
    } else {
      saveError.value = res?.error || 'Save failed'
    }
  } catch (e) {
    saveError.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
/* ── Modal Overlay ── */
.settings-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 10, 10, 0.6);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fade-in 0.15s ease-out;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.settings-modal {
  background: #FAFAFA;
  width: 580px;
  max-width: calc(100vw - 48px);
  max-height: calc(100vh - 80px);
  overflow-y: auto;
  border: 2px solid rgba(10,10,10,0.12);
  position: relative;
  animation: slide-in 0.2s ease-out;
  font-family: 'Space Mono', 'Courier New', monospace;
}

@keyframes slide-in {
  from { transform: translateY(-16px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

/* ── Header ── */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 22px;
  background: #0A0A0A;
  color: #FAFAFA;
}

.title-label {
  font-family: 'Space Mono', monospace;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 3px;
  text-transform: uppercase;
}

.close-btn {
  background: none;
  border: none;
  color: rgba(250,250,250,0.5);
  font-size: 14px;
  cursor: pointer;
  padding: 4px 8px;
  transition: color 0.1s;
}
.close-btn:hover { color: #FAFAFA; }

/* ── Warning Stripe ── */
.warning-stripe {
  height: 6px;
  background: repeating-linear-gradient(
    -45deg,
    #FF6B1A,
    #FF6B1A 10px,
    #FAFAFA 10px,
    #FAFAFA 20px
  );
}

/* ── Sections ── */
.settings-section {
  padding: 22px;
  border-bottom: 2px solid rgba(10,10,10,0.08);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.section-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.4);
}

/* ── Current Setup grid ── */
.setup-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 2px dashed rgba(10,10,10,0.1);
  padding: 12px 14px;
  background: #F5F5F5;
}
.setup-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  font-size: 12px;
  letter-spacing: 0.3px;
}
.setup-key {
  color: rgba(10,10,10,0.5);
  flex-shrink: 0;
}
.setup-val {
  color: #0A0A0A;
  font-weight: 700;
  text-align: right;
  overflow-wrap: anywhere;
}
.setup-aux {
  color: rgba(10,10,10,0.4);
  font-weight: 400;
  margin-left: 4px;
}
.setup-missing {
  color: #FF4444;
  font-weight: 400;
}

/* ── Status Badge ── */
.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
}

.badge-dot {
  width: 7px;
  height: 7px;
  background: rgba(10,10,10,0.2);
  border-radius: 0;
}
.status-badge.ok .badge-dot { background: #43C165; }
.status-badge.fail .badge-dot { background: #FF4444; }
.status-badge.ok { color: #43C165; }
.status-badge.fail { color: #FF4444; }
.status-badge.idle { color: rgba(10,10,10,0.3); }

/* ── Form Fields ── */
.field-row {
  margin-bottom: 14px;
}

.field-label {
  display: block;
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.5);
  margin-bottom: 6px;
}

.field-input {
  width: 100%;
  border: 2px solid rgba(10,10,10,0.1);
  background: #F5F5F5;
  padding: 8px 11px;
  font-family: 'Space Mono', monospace;
  font-size: 13px;
  color: #0A0A0A;
  outline: none;
  transition: border-color 0.1s;
  box-sizing: border-box;
}
.field-input:focus { border-color: #FF6B1A; background: #FAFAFA; }
.field-input::placeholder { color: rgba(10,10,10,0.3); }

.select-wrapper { position: relative; }
.field-select {
  width: 100%;
  border: 2px solid rgba(10,10,10,0.1);
  background: #F5F5F5;
  padding: 8px 11px;
  font-family: 'Space Mono', monospace;
  font-size: 13px;
  color: #0A0A0A;
  outline: none;
  cursor: pointer;
  appearance: auto;
  transition: border-color 0.1s;
  box-sizing: border-box;
}
.field-select:focus { border-color: #FF6B1A; }

/* ── Model input group ── */
.model-input-group {
  display: flex;
  gap: 6px;
}
.model-select-wrapper { flex: 1; min-width: 0; }

.load-models-btn {
  border: 2px solid rgba(10,10,10,0.1);
  background: #F5F5F5;
  padding: 8px 12px;
  font-family: 'Space Mono', monospace;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.1s;
  flex-shrink: 0;
}
.load-models-btn:hover:not(:disabled) { border-color: #FF6B1A; color: #FF6B1A; }
.load-models-btn:disabled { opacity: 0.35; cursor: not-allowed; }

/* ── Key input group ── */
.key-input-group {
  display: flex;
  gap: 6px;
}
.key-input-group .field-input { flex: 1; }

.toggle-key-btn {
  border: 2px solid rgba(10,10,10,0.1);
  background: #F5F5F5;
  padding: 8px 12px;
  font-size: 14px;
  cursor: pointer;
  flex-shrink: 0;
  transition: border-color 0.1s;
}
.toggle-key-btn:hover { border-color: #FF6B1A; }

.field-hint {
  margin-top: 5px;
  font-size: 11px;
  color: rgba(10,10,10,0.4);
  letter-spacing: 0.5px;
}
.field-hint a { color: #FF6B1A; text-decoration: underline; }

.field-error {
  margin-top: 5px;
  font-size: 11px;
  color: #FF4444;
}

/* ── Test row ── */
.test-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.test-btn {
  border: 2px solid rgba(10,10,10,0.12);
  background: transparent;
  padding: 8px 16px;
  font-family: 'Space Mono', monospace;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  cursor: pointer;
  transition: all 0.1s;
}
.test-btn:hover:not(:disabled) { border-color: #FF6B1A; color: #FF6B1A; }
.test-btn:disabled { opacity: 0.35; cursor: not-allowed; }

.test-result {
  font-size: 12px;
  letter-spacing: 1px;
}
.test-result.ok { color: #43C165; }
.test-result.fail { color: #FF4444; }

/* ── Advanced ── */
.advanced-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  background: transparent;
  border: none;
  padding: 0 0 10px 0;
  cursor: pointer;
  font-family: 'Space Mono', monospace;
}
.chevron {
  font-size: 16px;
  color: rgba(10,10,10,0.4);
  line-height: 1;
}
.advanced-body {
  margin-top: 4px;
}
.advanced-hint {
  font-size: 11px;
  color: rgba(10,10,10,0.4);
  margin-bottom: 12px;
  letter-spacing: 0.5px;
}
.advanced-group {
  padding: 10px 0;
  border-top: 1px dashed rgba(10,10,10,0.08);
}
.advanced-group:first-child { border-top: none; padding-top: 0; }
.advanced-group-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #0A0A0A;
  margin-bottom: 10px;
}

/* ── Footer ── */
.modal-footer {
  padding: 18px 22px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.save-error {
  font-size: 12px;
  color: #FF4444;
  letter-spacing: 0.5px;
}

.save-success {
  font-size: 12px;
  color: #43C165;
  letter-spacing: 1px;
}

.cancel-btn {
  border: 2px solid rgba(10,10,10,0.1);
  background: transparent;
  padding: 10px 20px;
  font-family: 'Space Mono', monospace;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  cursor: pointer;
  color: rgba(10,10,10,0.5);
  transition: all 0.1s;
}
.cancel-btn:hover { border-color: rgba(10,10,10,0.3); color: #0A0A0A; }

.save-btn {
  border: 2px solid #0A0A0A;
  background: #0A0A0A;
  color: #FAFAFA;
  padding: 10px 20px;
  font-family: 'Space Mono', monospace;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  cursor: pointer;
  transition: all 0.15s;
}
.save-btn:hover:not(:disabled) { background: #FF6B1A; border-color: #FF6B1A; }
.save-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── AI Integration (MCP) ── */
.ai-section {
  background: #F5F5F5;
}

.ai-intro {
  font-size: 12px;
  line-height: 1.5;
  color: rgba(10,10,10,0.65);
  margin-bottom: 14px;
}

.ai-loading,
.ai-error {
  font-size: 12px;
  padding: 12px 14px;
  border: 2px dashed rgba(10,10,10,0.1);
  background: #FAFAFA;
}

.ai-error {
  color: #FF4444;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.ai-retry {
  background: #0A0A0A;
  color: #FAFAFA;
  border: none;
  padding: 6px 12px;
  font-family: 'Space Mono', monospace;
  font-size: 11px;
  letter-spacing: 1px;
  text-transform: uppercase;
  cursor: pointer;
}

.ai-summary {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border: 2px dashed rgba(10,10,10,0.1);
  padding: 12px 14px;
  background: #FAFAFA;
  margin-bottom: 14px;
}

.ai-summary-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  font-size: 12px;
}

.ai-summary-key {
  color: rgba(10,10,10,0.5);
  flex-shrink: 0;
}

.ai-summary-val {
  color: #0A0A0A;
  font-weight: 700;
  text-align: right;
  overflow-wrap: anywhere;
}

.ai-error-text {
  color: #FF4444;
  font-weight: 400;
  font-size: 11px;
}

.ai-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 0;
  border-bottom: 2px solid rgba(10,10,10,0.08);
}

.ai-tab {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  padding: 8px 12px;
  font-family: 'Space Mono', monospace;
  font-size: 11px;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.45);
  cursor: pointer;
  transition: color 0.1s, border-color 0.1s;
}

.ai-tab:hover { color: #0A0A0A; }

.ai-tab.active {
  color: #0A0A0A;
  border-bottom-color: #FF6B1A;
}

.ai-client {
  padding-top: 14px;
}

.ai-client-file {
  font-size: 11px;
  color: rgba(10,10,10,0.55);
  margin-bottom: 8px;
  overflow-wrap: anywhere;
}

.ai-client-file-label {
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-right: 4px;
}

.ai-client-file-path {
  font-family: 'Space Mono', monospace;
  color: #0A0A0A;
  background: #FAFAFA;
  padding: 1px 5px;
  border: 1px solid rgba(10,10,10,0.08);
}

.ai-snippet-wrap {
  position: relative;
}

.ai-snippet {
  background: #0A0A0A;
  color: #FAFAFA;
  padding: 14px 16px;
  margin: 0;
  font-family: 'Space Mono', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.45;
  overflow-x: auto;
  white-space: pre;
  border: 2px solid #0A0A0A;
}

.ai-snippet code {
  font: inherit;
  color: inherit;
}

.ai-copy-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  background: #FAFAFA;
  color: #0A0A0A;
  border: 1px solid rgba(250,250,250,0.2);
  padding: 4px 10px;
  font-family: 'Space Mono', monospace;
  font-size: 10px;
  letter-spacing: 1px;
  text-transform: uppercase;
  cursor: pointer;
  transition: background 0.1s, color 0.1s;
}

.ai-copy-btn:hover { background: #FF6B1A; color: #FAFAFA; }
.ai-copy-btn.ok { background: #43C165; color: #FAFAFA; }
.ai-copy-btn.fail { background: #FF4444; color: #FAFAFA; }

.ai-client-notes {
  font-size: 11px;
  color: rgba(10,10,10,0.55);
  margin-top: 8px;
  line-height: 1.5;
}

.ai-tools-toggle {
  display: block;
  width: 100%;
  background: none;
  border: 2px dashed rgba(10,10,10,0.1);
  padding: 8px 12px;
  margin-top: 14px;
  font-family: 'Space Mono', monospace;
  font-size: 11px;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.55);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.1s, color 0.1s;
}

.ai-tools-toggle:hover {
  border-color: rgba(10,10,10,0.3);
  color: #0A0A0A;
}

.ai-tools-list {
  list-style: none;
  padding: 12px 14px;
  margin: 6px 0 0 0;
  background: #FAFAFA;
  border: 2px dashed rgba(10,10,10,0.1);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-tool {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 12px;
  font-size: 11px;
  line-height: 1.5;
}

.ai-tool-name {
  color: #FF6B1A;
  font-weight: 700;
  font-family: 'Space Mono', monospace;
}

.ai-tool-desc {
  color: rgba(10,10,10,0.7);
  overflow-wrap: anywhere;
}

.ai-docs-link {
  font-size: 11px;
  color: rgba(10,10,10,0.55);
  margin-top: 14px;
  text-align: right;
}

.ai-docs-link a {
  color: #0A0A0A;
  font-weight: 700;
  text-decoration: none;
  border-bottom: 1px solid #FF6B1A;
}

.ai-docs-link a:hover { color: #FF6B1A; }

@media (max-width: 480px) {
  .ai-tool {
    grid-template-columns: 1fr;
    gap: 2px;
  }
}
</style>
