<template>
  <div class="home-container">
    <!-- Top Navigation Bar -->
    <nav class="navbar">
      <div class="nav-brand">MIROSHARK</div>
      <div class="nav-links">
        <router-link to="/explore" class="explore-link" title="Browse public simulations">
          <span class="compass">◎</span> Explore
        </router-link>
        <a href="https://github.com/aaronjmars/MiroShark" target="_blank" class="github-link">
          GitHub <span class="arrow">↗</span>
        </a>
        <button class="settings-btn" @click="settingsOpen = true" title="Settings">
          ⚙
        </button>
      </div>
    </nav>

    <SettingsPanel :open="settingsOpen" @close="settingsOpen = false" />

    <!-- Document preview modal (URL fetches + Ask-mode generations) -->
    <Teleport to="body">
      <div v-if="previewDoc" class="doc-preview-overlay" @click.self="previewDoc = null">
        <div class="doc-preview-modal">
          <div class="doc-preview-header">
            <div class="doc-preview-title">
              <span class="doc-preview-icon">◈</span>
              <span>{{ previewDoc.title }}</span>
            </div>
            <button class="doc-preview-close" @click="previewDoc = null">✕</button>
          </div>
          <div class="doc-preview-warning"></div>
          <div class="doc-preview-meta">
            {{ previewDoc.char_count.toLocaleString() }} chars
            <span v-if="previewDoc.url" class="doc-preview-meta-sep">·</span>
            <span v-if="previewDoc.url" class="doc-preview-url">{{ previewDoc.url }}</span>
          </div>
          <pre class="doc-preview-body">{{ previewDoc.text }}</pre>
        </div>
      </div>
    </Teleport>

    <div class="main-content">
      <!-- Upper Section: Hero Area -->
      <section class="hero-section">
        <div class="tag-row">
          <span class="orange-tag">Universal Swarm Intelligence Engine</span>
        </div>

        <h1 class="main-title">
          <span class="gradient-text">Simulate anything, for $1</span>
        </h1>

        <div class="hero-desc">
          <p>
            Drop in anything — a press release, a news headline, a policy draft, a question you can't answer, a historical what-if — and <span class="highlight-bold">MiroShark</span> spawns <span class="highlight-orange">hundreds of agents</span> that react to it hour by hour. Posting, arguing, trading, changing their minds.
          </p>
          <p class="slogan-text">
            Don't predict the future. Simulate it<span class="blinking-cursor">_</span>
          </p>
        </div>

        <div class="decoration-square"></div>

        <button class="scroll-down-btn" @click="scrollToBottom">
          ↓
        </button>
      </section>

      <!-- Lower Section: Two-Column Layout -->
      <section class="dashboard-section">
        <!-- Left Column: Status & Steps -->
        <div class="left-panel">
          <div class="panel-header">
            <span class="status-dot">■</span> System Status
          </div>
          
          <h2 class="section-title">Ready</h2>
          <p class="section-desc">
            First simulation in ~10 min, ~$1 on the cloud preset. Drop in a doc or pick a trending headline to start.
          </p>


          <!-- What it does (from README) -->
          <div class="steps-container">
            <div class="steps-header">
               <span class="diamond-icon">◇</span> What it does
            </div>
            <div class="workflow-list">
              <div class="workflow-item">
                <span class="step-num">01</span>
                <div class="step-info">
                  <div class="step-title">You bring a scenario</div>
                  <div class="step-desc">MiroShark builds the world around it — extracts actors, stakes, and open questions from your input.</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">02</span>
                <div class="step-info">
                  <div class="step-title">Hundreds of grounded agents</div>
                  <div class="step-desc">React on Twitter, Reddit, and a prediction market. Hour by hour, round after round.</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">03</span>
                <div class="step-info">
                  <div class="step-title">Steer the timeline</div>
                  <div class="step-desc">Chat with any agent. Drop breaking news mid-run. Fork a counterfactual and watch it diverge.</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">04</span>
                <div class="step-info">
                  <div class="step-title">Get a report</div>
                  <div class="step-desc">A Substack-style write-up of what happened, citing actual posts and trades from the run.</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Right Column: Interactive Console -->
        <div class="right-panel">
          <div class="console-box">
            <!-- Upload Area -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">01 / Reality Seeds</span>
                <span class="console-meta">Supported formats: PDF, MD, TXT</span>
              </div>
              
              <div 
                class="upload-zone"
                :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
              >
                <input
                  ref="fileInput"
                  type="file"
                  multiple
                  accept=".pdf,.md,.txt"
                  @change="handleFileSelect"
                  style="display: none"
                  :disabled="loading"
                />
                
                <div v-if="files.length === 0" class="upload-placeholder">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">Drop Files to Upload</div>
                  <div class="upload-hint">or click to browse the file system</div>
                </div>
                
                <div v-else class="file-list">
                  <div v-for="(file, index) in files" :key="index" class="file-item">
                    <span class="file-icon">📄</span>
                    <span class="file-name">{{ file.name }}</span>
                    <button @click.stop="removeFile(index)" class="remove-btn">×</button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Ask Mode (no document needed) -->
            <div class="console-section url-section">
              <div class="console-header">
                <span class="console-label">01a / Just Ask</span>
                <span class="console-meta">No document? Type a question, we synthesize a briefing.</span>
              </div>
              <div class="url-input-row">
                <input
                  v-model="askQuestion"
                  class="url-input"
                  type="text"
                  placeholder="e.g. Will the EU AI Act's biometrics clause survive the final trilogue?"
                  :disabled="loading || askBusy"
                  @keydown.enter.prevent="runAskMode"
                />
                <button
                  class="url-fetch-btn"
                  @click="runAskMode"
                  :disabled="!askQuestion.trim() || loading || askBusy"
                >
                  <span v-if="askBusy">...</span>
                  <span v-else>Research →</span>
                </button>
              </div>
              <div v-if="askError" class="url-error">{{ askError }}</div>
              <div v-if="askBusy" class="url-doc-meta" style="margin-top:6px">Synthesizing briefing — this uses the Smart model and takes ~20–30s.</div>
              <div v-if="askDocs.length > 0" class="url-doc-list">
                <div
                  v-for="doc in askDocs"
                  :key="doc.url"
                  class="url-doc-item"
                  role="button"
                  tabindex="0"
                  title="Click to preview the generated briefing"
                  @click="previewDoc = doc"
                  @keydown.enter.prevent="previewDoc = doc"
                  @keydown.space.prevent="previewDoc = doc"
                >
                  <span class="url-doc-icon">◈</span>
                  <div class="url-doc-info">
                    <div class="url-doc-title" :title="doc.title">{{ truncate(doc.title, 70) }}</div>
                    <div class="url-doc-meta" :title="doc.url">{{ doc.char_count.toLocaleString() }} chars · {{ truncate(doc.url, 72) }}</div>
                  </div>
                  <button @click.stop="removeUrlDocByRef(doc)" class="remove-btn">×</button>
                </div>
              </div>
            </div>

            <!-- URL Input Section -->
            <div class="console-section url-section">
              <div class="console-header">
                <span class="console-label">01b / URL Import</span>
                <span class="console-meta">Paste article or report URL</span>
              </div>
              <div class="url-input-row">
                <input
                  v-model="urlInput"
                  class="url-input"
                  type="url"
                  placeholder="https://example.com/article"
                  :disabled="loading || urlFetching"
                  @keydown.enter.prevent="fetchUrlDoc"
                />
                <button
                  class="url-fetch-btn"
                  @click="fetchUrlDoc"
                  :disabled="!urlInput.trim() || loading || urlFetching"
                >
                  <span v-if="urlFetching">...</span>
                  <span v-else>Fetch →</span>
                </button>
              </div>
              <div v-if="urlError" class="url-error">{{ urlError }}</div>
              <div v-if="fetchedDocs.length > 0" class="url-doc-list">
                <div
                  v-for="doc in fetchedDocs"
                  :key="doc.url"
                  class="url-doc-item"
                  role="button"
                  tabindex="0"
                  title="Click to preview the extracted content"
                  @click="previewDoc = doc"
                  @keydown.enter.prevent="previewDoc = doc"
                  @keydown.space.prevent="previewDoc = doc"
                >
                  <span class="url-doc-icon">◈</span>
                  <div class="url-doc-info">
                    <div class="url-doc-title" :title="doc.title">{{ truncate(doc.title, 70) }}</div>
                    <div class="url-doc-meta" :title="doc.url">{{ doc.char_count.toLocaleString() }} chars · {{ truncate(doc.url, 72) }}</div>
                  </div>
                  <button @click.stop="removeUrlDocByRef(doc)" class="remove-btn">×</button>
                </div>
              </div>
              <TrendingTopics
                :busy="urlFetching"
                @select="handleTrendingSelect"
              />
            </div>

            <!-- Divider -->
            <div class="console-divider">
              <span>Input Parameters</span>
            </div>

            <!-- Input Area -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">>_ 02 / Simulation Prompt</span>
              </div>
              <ScenarioSuggestions
                :text-preview="scenarioSuggestPreview"
                :simulation-prompt="formData.simulationRequirement"
                @use="handleSuggestionUse"
              />
              <div class="input-wrapper">
                <textarea
                  v-model="formData.simulationRequirement"
                  class="code-input"
                  placeholder="// Enter your simulation or prediction requirements in natural language (e.g., If a university announces the revocation of a disciplinary action against a student, what public opinion trends will emerge?)"
                  rows="6"
                  :disabled="loading"
                ></textarea>
                <div class="model-badge">Engine: MiroShark-V1.0</div>
              </div>
            </div>

            <!-- Start Button -->
            <div class="console-section btn-section">
              <button 
                class="start-engine-btn"
                @click="startSimulation"
                :disabled="!canSubmit || loading"
              >
                <span v-if="!loading">Launch Simulation</span>
                <span v-else>Initializing...</span>
                <span class="btn-arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Quick Start Templates -->
      <TemplateGallery />

      <!-- History Project Database -->
      <HistoryDatabase />

    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import TemplateGallery from '../components/TemplateGallery.vue'
import SettingsPanel from '../components/SettingsPanel.vue'
import ScenarioSuggestions from '../components/ScenarioSuggestions.vue'
import TrendingTopics from '../components/TrendingTopics.vue'
import { fetchUrl } from '../api/graph'
import { askMode } from '../api/simulation'

const settingsOpen = ref(false)
const previewDoc = ref(null)

const router = useRouter()

// Form data
const formData = ref({
  simulationRequirement: ''
})

// File list
const files = ref([])

// URL import state
const urlInput = ref('')
const urlDocs = ref([])   // [{title, url, text, char_count}]
const urlFetching = ref(false)
const urlError = ref('')

// Ask-mode state — question-only pipeline
const askQuestion = ref('')
const askBusy = ref(false)
const askError = ref('')

// State
const loading = ref(false)
const error = ref('')
const isDragOver = ref(false)

// File input ref
const fileInput = ref(null)

// Computed: whether the form can be submitted
const canSubmit = computed(() => {
  return formData.value.simulationRequirement.trim() !== '' &&
    (files.value.length > 0 || urlDocs.value.length > 0)
})

// Trigger file selection
const triggerFileInput = () => {
  if (!loading.value) {
    fileInput.value?.click()
  }
}

// Handle file selection
const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

// Handle drag-related events
const handleDragOver = (e) => {
  if (!loading.value) {
    isDragOver.value = true
  }
}

const handleDragLeave = (e) => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  
  const droppedFiles = Array.from(e.dataTransfer.files)
  addFiles(droppedFiles)
}

// Client-readable file previews (.md / .txt), keyed by File identity so we
// don't re-read when the `files` array gets reordered. PDFs are skipped here
// — their text is extracted server-side during graph build, so they simply
// won't trigger scenario auto-suggest on their own. A .md/.txt sibling (or a
// URL doc) will still drive suggestions.
const filePreviewText = ref('')

const refreshFilePreviewText = async () => {
  const textish = files.value.filter(f => {
    const ext = (f.name.split('.').pop() || '').toLowerCase()
    return ext === 'md' || ext === 'txt'
  })
  if (textish.length === 0) {
    filePreviewText.value = ''
    return
  }

  try {
    const chunks = await Promise.all(textish.map(async (f) => {
      try {
        // Only read the first ~6KB per file to keep the combined preview
        // bounded. The backend further clamps to 2000 chars.
        const slice = f.slice ? f.slice(0, 6000) : f
        const txt = await slice.text()
        return (txt || '').slice(0, 3000)
      } catch (_) {
        return ''
      }
    }))
    filePreviewText.value = chunks.filter(Boolean).join('\n\n').slice(0, 6000)
  } catch (_) {
    filePreviewText.value = ''
  }
}

// Add files
const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt'].includes(ext)
  })
  files.value.push(...validFiles)
  refreshFilePreviewText()
}

// Remove file
const removeFile = (index) => {
  files.value.splice(index, 1)
  refreshFilePreviewText()
}

// Combined text preview handed to ScenarioSuggestions.  Includes every
// fetched URL's extracted text plus any client-side-readable file text.
// Kept to ~6KB on the client; the backend trims again.
const scenarioSuggestPreview = computed(() => {
  const urlChunks = (urlDocs.value || [])
    .map(d => {
      const head = d.title ? `# ${d.title}\n` : ''
      const body = (d.text || '').slice(0, 3000)
      return body ? head + body : ''
    })
    .filter(Boolean)

  const combined = [...urlChunks]
  if (filePreviewText.value) combined.push(filePreviewText.value)
  return combined.join('\n\n').slice(0, 6000)
})

// User picked one of the 3 scenario cards — fill the textarea but don't
// submit.  We overwrite whatever was there (including any earlier pick); if
// the user had already typed a partial scenario they can undo with Ctrl+Z.
const handleSuggestionUse = ({ question }) => {
  if (!question) return
  formData.value.simulationRequirement = question
}

// Scroll to bottom
const scrollToBottom = () => {
  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: 'smooth'
  })
}

// Fetch a URL and add it to urlDocs
const fetchUrlDoc = async () => {
  const url = urlInput.value.trim()
  if (!url || urlFetching.value) return

  // Prevent duplicate URLs
  if (urlDocs.value.some(d => d.url === url)) {
    urlError.value = 'This URL has already been added.'
    return
  }

  urlFetching.value = true
  urlError.value = ''
  try {
    const res = await fetchUrl(url)
    if (res.success) {
      urlDocs.value.push(res.data)
      urlInput.value = ''
    } else {
      urlError.value = res.error || 'Failed to fetch URL.'
    }
  } catch (err) {
    urlError.value = err.message || 'Failed to fetch URL.'
  } finally {
    urlFetching.value = false
  }
}

// Ask mode: ask → synthesized briefing becomes a url_doc; we also prefill the
// simulation_requirement textarea with the LLM's framing. Rest of the flow is
// unchanged.
const runAskMode = async () => {
  const q = askQuestion.value.trim()
  if (!q || askBusy.value) return
  askBusy.value = true
  askError.value = ''
  try {
    const res = await askMode(q)
    if (!res.success) {
      askError.value = res.error || 'Ask mode failed.'
      return
    }
    const d = res.data
    const synthUrl = `miroshark://ask/${encodeURIComponent(q.slice(0, 64))}`
    // Don't duplicate if re-run.
    const idx = urlDocs.value.findIndex(x => x.url === synthUrl)
    const payload = {
      title: d.title,
      url: synthUrl,
      text: d.seed_document,
      char_count: (d.seed_document || '').length,
    }
    if (idx >= 0) urlDocs.value.splice(idx, 1, payload)
    else urlDocs.value.push(payload)
    if (!formData.value.simulationRequirement) {
      formData.value.simulationRequirement = d.simulation_requirement
    }
    askQuestion.value = ''
  } catch (err) {
    askError.value = err?.response?.data?.error || err?.message || 'Ask mode failed.'
  } finally {
    askBusy.value = false
  }
}

// User picked a "What's Trending" card — push the URL into the input and
// reuse the existing fetch pipeline. ScenarioSuggestions already watches
// urlDocs and will fire once the fetched doc lands, so the user goes from
// blank-page to three scenario cards in one click.
const handleTrendingSelect = ({ url }) => {
  if (!url || urlFetching.value) return
  if (urlDocs.value.some(d => d.url === url)) {
    urlError.value = 'This URL is already loaded.'
    return
  }
  urlInput.value = url
  urlError.value = ''
  fetchUrlDoc()
}

// Remove a URL document from the list
const removeUrlDoc = (index) => {
  urlDocs.value.splice(index, 1)
}

const removeUrlDocByRef = (doc) => {
  const idx = urlDocs.value.indexOf(doc)
  if (idx >= 0) urlDocs.value.splice(idx, 1)
}

// Hard-cap display strings so long titles / deep URLs can't widen the
// doc-list row (CSS ellipsis can fail when intermediate flex ancestors
// don't propagate min-width:0).
const truncate = (s, max) => {
  if (!s) return ''
  return s.length > max ? s.slice(0, max - 1).trimEnd() + '…' : s
}

// Split docs by origin — Ask-synthesized briefings show under Just Ask,
// real URL fetches show under URL Import.
const askDocs = computed(() =>
  urlDocs.value.filter(d => typeof d.url === 'string' && d.url.startsWith('miroshark://ask/'))
)
const fetchedDocs = computed(() =>
  urlDocs.value.filter(d => !(typeof d.url === 'string' && d.url.startsWith('miroshark://ask/')))
)

// Start simulation - navigate immediately, API calls happen on the Process page
const startSimulation = () => {
  if (!canSubmit.value || loading.value) return

  // Store data pending upload
  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(files.value, formData.value.simulationRequirement, urlDocs.value)

    // Navigate immediately to Process page (using special identifier for new project)
    router.push({
      name: 'Process',
      params: { projectId: 'new' }
    })
  })
}
</script>

<style scoped>
/* ═══════════════════════════════════════════════════════════
   HOME — Hyperstitions Design System applied
   ═══════════════════════════════════════════════════════════ */

.home-container {
  min-height: 100vh;
  background: var(--background);
  font-family: var(--font-display);
  color: var(--foreground);
}

/* ── Top Navigation ── */
.navbar {
  height: var(--space-xl);
  background: var(--color-black);
  color: var(--color-white);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 var(--space-lg);
}

.nav-brand {
  font-family: var(--font-mono);
  font-weight: 700;
  letter-spacing: 3px;
  font-size: 14px;
  text-transform: uppercase;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.explore-link {
  color: var(--color-white);
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 13px;
  letter-spacing: 1px;
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  transition: var(--transition-fast);
  opacity: 0.6;
}

.explore-link:hover { opacity: 1; color: var(--color-orange); }

.compass { font-size: 15px; line-height: 1; }

.github-link {
  color: var(--color-white);
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 13px;
  letter-spacing: 1px;
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  transition: var(--transition-fast);
  opacity: 0.6;
}

.github-link:hover { opacity: 1; }

.arrow { font-family: sans-serif; }

.settings-btn {
  background: none;
  border: none;
  color: rgba(250,250,250,0.5);
  font-size: 18px;
  cursor: pointer;
  padding: 0 0 0 var(--space-md);
  line-height: 1;
  transition: var(--transition-fast);
}

.settings-btn:hover { color: var(--color-orange); }

/* ── Main Content ── */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: var(--space-2xl) var(--space-lg);
}

/* ── Hero Section ── */
.hero-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  margin-bottom: var(--space-2xl);
  position: relative;
}

.tag-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-md);
  font-family: var(--font-mono);
  font-size: 13px;
}

.orange-tag {
  background: var(--color-orange);
  color: var(--color-white);
  padding: 4px var(--space-sm);
  font-weight: 700;
  letter-spacing: 3px;
  font-size: 11px;
  text-transform: uppercase;
  font-family: var(--font-mono);
}

.main-title {
  font-family: var(--font-display);
  font-size: 50px;
  line-height: 1.25;
  font-weight: 400;
  margin: 0 0 var(--space-lg) 0;
  letter-spacing: -1px;
  color: var(--foreground);
}

.gradient-text {
  color: var(--color-orange);
  -webkit-text-fill-color: var(--color-orange);
  display: inline;
}

.hero-desc {
  font-family: var(--font-display);
  font-size: 22px;
  line-height: 1.5;
  color: rgba(10,10,10,0.7);
  max-width: 640px;
  margin-bottom: var(--space-xl);
}

.hero-desc p { margin-bottom: var(--space-md); }

.highlight-bold {
  color: var(--foreground);
  font-weight: 400;
}

.highlight-orange {
  color: var(--color-orange);
  font-family: var(--font-mono);
  font-size: 0.85em;
}

.highlight-code {
  background: rgba(10,10,10,0.05);
  padding: 2px var(--space-xs);
  font-family: var(--font-mono);
  font-size: 0.85em;
  color: var(--foreground);
}

.slogan-text {
  font-family: var(--font-display);
  font-size: 25px;
  line-height: 1.5;
  color: var(--foreground);
  border-left: var(--border-orange);
  padding-left: var(--space-md);
  margin-top: var(--space-md);
}

.blinking-cursor {
  color: var(--color-green);
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.decoration-square {
  width: var(--space-sm);
  height: var(--space-sm);
  background: var(--color-green);
  margin-top: var(--space-md);
}

.scroll-down-btn {
  margin-top: var(--space-md);
  width: var(--space-lg);
  height: var(--space-lg);
  border: var(--border-medium);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--color-orange);
  font-size: 1.2rem;
  transition: var(--transition-fast);
}

.scroll-down-btn:hover {
  border-color: var(--color-orange);
}

/* ── Warning Stripe Divider ── */
.dashboard-section::before {
  content: '';
  display: block;
  height: 7px;
  background: repeating-linear-gradient(
    -45deg,
    var(--color-orange),
    var(--color-orange) 11px,
    var(--background) 11px,
    var(--background) 22px
  );
  margin-bottom: var(--space-xl);
}

/* ── Dashboard Section ── */
.dashboard-section {
  display: flex;
  gap: var(--space-xl);
  padding-top: 0;
  align-items: flex-start;
}

.dashboard-section .left-panel,
.dashboard-section .right-panel {
  display: flex;
  flex-direction: column;
}

/* ── Left Panel ── */
.left-panel { flex: 0.8; }

.panel-header {
  font-family: var(--font-mono);
  font-size: 14px;
  color: rgba(10,10,10,0.4);
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  margin-bottom: var(--space-md);
  letter-spacing: 3px;
  text-transform: uppercase;
}

.status-dot {
  color: var(--color-green);
  font-size: 0.8rem;
}

.section-title {
  font-family: var(--font-display);
  font-size: 34px;
  font-weight: 400;
  margin: 0 0 var(--space-sm) 0;
}

.section-desc {
  color: rgba(10,10,10,0.5);
  font-family: var(--font-display);
  font-size: 22px;
  margin-bottom: var(--space-md);
  line-height: 1.5;
}

/* ── Metric Cards ── */
.metrics-row {
  display: flex;
  gap: var(--space-md);
  margin-bottom: var(--space-md);
}

.metric-card {
  border: var(--border-light);
  padding: var(--space-md) var(--space-lg);
  min-width: 150px;
  transition: var(--transition-fast);
}

.metric-card:hover { border-color: var(--color-orange); }

.metric-value {
  font-family: var(--font-display);
  font-size: 31px;
  margin-bottom: var(--space-xs);
}

.metric-label {
  font-family: var(--font-mono);
  font-size: 13px;
  color: rgba(10,10,10,0.4);
  letter-spacing: 1px;
}

/* ── Workflow Steps ── */
.steps-container {
  border: var(--border-light);
  padding: var(--space-lg);
  position: relative;
}

/* Corner markers */
.steps-container::before,
.steps-container::after {
  content: '';
  position: absolute;
  width: 20px;
  height: 20px;
  pointer-events: none;
}
.steps-container::before {
  top: 12px; left: 12px;
  border-top: 3px solid var(--color-orange);
  border-left: 3px solid var(--color-orange);
}
.steps-container::after {
  bottom: 12px; right: 12px;
  border-bottom: 3px solid var(--color-green);
  border-right: 3px solid var(--color-green);
}

.steps-header {
  font-family: var(--font-mono);
  font-size: 14px;
  color: rgba(10,10,10,0.4);
  margin-bottom: var(--space-md);
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  letter-spacing: 3px;
  text-transform: uppercase;
}

.diamond-icon {
  color: var(--color-orange);
  font-size: 1.2rem;
}

.workflow-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.workflow-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-md);
}

.step-num {
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 15px;
  color: var(--color-orange);
  opacity: 0.5;
}

.step-info { flex: 1; }

.step-title {
  font-family: var(--font-display);
  font-size: 22px;
  margin-bottom: 4px;
}

.step-desc {
  font-family: var(--font-mono);
  font-size: 13px;
  color: rgba(10,10,10,0.4);
  line-height: 1.6;
}

/* ── Right Console ── */
.right-panel { flex: 1.2; }

.console-box {
  border: var(--border-medium);
  padding: var(--space-xs);
  position: relative;
}

/* Console corner markers */
.console-box::before,
.console-box::after {
  content: '';
  position: absolute;
  width: 20px;
  height: 20px;
  pointer-events: none;
}
.console-box::before {
  top: -2px; right: -2px;
  border-top: 3px solid var(--color-orange);
  border-right: 3px solid var(--color-orange);
}
.console-box::after {
  bottom: -2px; left: -2px;
  border-bottom: 3px solid var(--color-green);
  border-left: 3px solid var(--color-green);
}

.console-section { padding: var(--space-md); }
.console-section.btn-section { padding-top: 0; }

.console-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--space-sm);
  font-family: var(--font-mono);
  font-size: 13px;
  color: rgba(10,10,10,0.4);
  letter-spacing: 1px;
}

.console-label { text-transform: uppercase; }
.console-meta { font-size: 11px; }

/* ── Upload Zone ── */
.upload-zone {
  border: 2px dashed rgba(10,10,10,0.12);
  height: 200px;
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: var(--transition-medium);
  background: var(--color-gray);
}

.upload-zone.has-files { align-items: flex-start; }

.upload-zone:hover {
  border-color: var(--color-orange);
  background: var(--background);
}

.upload-zone.drag-over {
  border-color: var(--color-green);
  background: rgba(67,193,101,0.05);
}

.upload-placeholder { text-align: center; }

.upload-icon {
  width: var(--space-lg);
  height: var(--space-lg);
  border: var(--border-medium);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto var(--space-sm);
  color: var(--color-orange);
  font-size: 1.2rem;
}

.upload-title {
  font-family: var(--font-display);
  font-size: 18px;
  margin-bottom: var(--space-xs);
}

.upload-hint {
  font-family: var(--font-mono);
  font-size: 13px;
  color: rgba(10,10,10,0.35);
}

/* ── File List ── */
.file-list {
  width: 100%;
  padding: var(--space-sm);
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.file-item {
  display: flex;
  align-items: center;
  background: var(--background);
  padding: var(--space-xs) var(--space-sm);
  border: var(--border-light);
  font-family: var(--font-mono);
  font-size: 14px;
}

.file-name { flex: 1; margin: 0 var(--space-sm); }

.remove-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
  color: rgba(10,10,10,0.35);
  transition: var(--transition-fast);
}

.remove-btn:hover { color: var(--color-red); }

/* ── Console Divider ── */
.console-divider {
  display: flex;
  align-items: center;
  margin: var(--space-sm) 0;
}

.console-divider::before,
.console-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: rgba(10,10,10,0.08);
}

.console-divider span {
  padding: 0 var(--space-sm);
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.25);
  letter-spacing: 3px;
  text-transform: uppercase;
}

/* ── Text Input ── */
.input-wrapper {
  position: relative;
  border: var(--border-light);
  background: var(--color-gray);
  transition: var(--transition-fast);
}

.input-wrapper:focus-within {
  border-color: var(--color-orange);
}

.code-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: var(--space-md);
  font-family: var(--font-mono);
  font-size: 15px;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  min-height: 150px;
  color: var(--foreground);
}

.code-input::placeholder {
  color: rgba(10,10,10,0.35);
}

.model-badge {
  position: absolute;
  bottom: var(--space-xs);
  right: var(--space-sm);
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.25);
  letter-spacing: 1px;
}

/* ── Launch Button ── */
.start-engine-btn {
  width: 100%;
  background: var(--color-black);
  color: var(--color-white);
  border: 2px solid var(--color-black);
  padding: 20px var(--space-lg);
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.15s ease;
  letter-spacing: 3px;
  text-transform: uppercase;
  position: relative;
  overflow: hidden;
}

.start-engine-btn:not(:disabled) {
  animation: btn-pulse 2s ease-in-out infinite;
}

.start-engine-btn:hover:not(:disabled) {
  background: var(--color-orange);
  border-color: var(--color-orange);
}

.start-engine-btn:active:not(:disabled) {
  opacity: 0.9;
}

.start-engine-btn:disabled {
  background: var(--color-gray);
  color: rgba(10,10,10,0.35);
  cursor: not-allowed;
  border-color: rgba(10,10,10,0.08);
}

@keyframes btn-pulse {
  0%, 100% { border-color: var(--color-black); }
  50% { border-color: var(--color-orange); }
}

/* ── URL Import Section ── */
.url-section {
  padding-top: 0;
}

.url-input-row {
  display: flex;
  gap: var(--space-xs);
}

.url-input {
  flex: 1;
  border: var(--border-light);
  background: var(--color-gray);
  padding: var(--space-xs) var(--space-sm);
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--foreground);
  outline: none;
  transition: var(--transition-fast);
  min-width: 0;
}

.url-input:focus {
  border-color: var(--color-orange);
  background: var(--background);
}

.url-input::placeholder {
  color: rgba(10,10,10,0.3);
}

.url-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.url-fetch-btn {
  background: var(--color-black);
  color: var(--color-white);
  border: 2px solid var(--color-black);
  padding: var(--space-xs) var(--space-sm);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 1px;
  cursor: pointer;
  transition: var(--transition-fast);
  white-space: nowrap;
}

.url-fetch-btn:hover:not(:disabled) {
  background: var(--color-orange);
  border-color: var(--color-orange);
}

.url-fetch-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.url-error {
  margin-top: var(--space-xs);
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-red);
}

.url-doc-list {
  margin-top: var(--space-xs);
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.url-doc-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-xs);
  background: var(--background);
  padding: var(--space-xs) var(--space-sm);
  border: var(--border-light);
  border-left: 3px solid var(--color-green);
  cursor: pointer;
  transition: background 0.1s, border-left-color 0.1s;
}
.url-doc-item:hover,
.url-doc-item:focus-visible {
  background: rgba(67, 193, 101, 0.06);
  border-left-color: var(--color-orange);
  outline: none;
}

.url-doc-icon {
  color: var(--color-green);
  font-size: 14px;
  margin-top: 1px;
  flex-shrink: 0;
}

.url-doc-info {
  flex: 1;
  min-width: 0;
}

.url-doc-title {
  font-family: var(--font-display);
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.url-doc-meta {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.35);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Footer ── */
.attribution-footer {
  text-align: center;
  padding: var(--space-lg) 0;
  font-family: var(--font-mono);
  font-size: 13px;
  color: rgba(10,10,10,0.25);
  letter-spacing: 1px;
}

.attribution-footer a {
  color: rgba(10,10,10,0.4);
  text-decoration: none;
}

.attribution-footer a:hover {
  color: var(--color-orange);
}

/* ── Doc Preview Modal ── */
.doc-preview-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 10, 10, 0.65);
  z-index: 1050;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  animation: doc-preview-fade 0.12s ease-out;
}
@keyframes doc-preview-fade {
  from { opacity: 0; }
  to   { opacity: 1; }
}
.doc-preview-modal {
  background: #FAFAFA;
  width: 760px;
  max-width: 100%;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  border: 2px solid rgba(10,10,10,0.12);
  font-family: 'Space Mono', 'Courier New', monospace;
}
.doc-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px;
  background: #0A0A0A;
  color: #FAFAFA;
}
.doc-preview-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 1px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.doc-preview-icon { color: #43C165; flex-shrink: 0; }
.doc-preview-close {
  background: none;
  border: none;
  color: rgba(250,250,250,0.6);
  font-size: 14px;
  cursor: pointer;
  padding: 4px 8px;
  flex-shrink: 0;
}
.doc-preview-close:hover { color: #FAFAFA; }
.doc-preview-warning {
  height: 6px;
  background: repeating-linear-gradient(
    -45deg,
    #FF6B1A,
    #FF6B1A 10px,
    #FAFAFA 10px,
    #FAFAFA 20px
  );
}
.doc-preview-meta {
  padding: 12px 20px;
  font-size: 11px;
  letter-spacing: 0.5px;
  color: rgba(10,10,10,0.45);
  border-bottom: 2px solid rgba(10,10,10,0.08);
  overflow-wrap: anywhere;
}
.doc-preview-meta-sep { margin: 0 6px; }
.doc-preview-url { color: #FF6B1A; }
.doc-preview-body {
  margin: 0;
  padding: 18px 20px;
  flex: 1;
  overflow-y: auto;
  font-family: 'Space Mono', 'Courier New', monospace;
  font-size: 12.5px;
  line-height: 1.6;
  color: #0A0A0A;
  white-space: pre-wrap;
  word-break: break-word;
  background: #FAFAFA;
}

/* ── Responsive ── */
@media (max-width: 1024px) {
  .dashboard-section { flex-direction: column; }
  .main-title { font-size: 34px; }
}
</style>
