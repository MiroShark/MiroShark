<template>
  <div class="ms-home">
    <!-- Deep-space background — scoped to this view only, doesn't touch
         the global App.vue theme. -->
    <div class="ms-space-bg" aria-hidden></div>
    <div class="ms-space-stars" aria-hidden></div>

    <!-- ── Top Navigation ── -->
    <nav class="ms-nav">
      <router-link to="/" class="ms-brand">
        <img src="/shark.webp" alt="" class="ms-brand-mark" />
        <span>MiroShark</span>
      </router-link>
      <div class="ms-nav-links">
        <router-link to="/explore" class="ms-nav-link" :title="$tr('Browse public simulations', '浏览公开模拟')">
          {{ $tr('Explore', '浏览') }}
        </router-link>
        <a href="https://github.com/aaronjmars/MiroShark" target="_blank" rel="noopener" class="ms-nav-link">
          GitHub <span class="ms-nav-arrow">↗</span>
        </a>
        <LocaleToggle />
        <button class="ms-nav-icon" @click="settingsOpen = true" :title="$tr('Settings', '设置')" aria-label="Settings">
          ⚙
        </button>
      </div>
    </nav>

    <SettingsPanel :open="settingsOpen" @close="settingsOpen = false" />

    <!-- Template auto-launch toast — visible briefly while a ?template= link
         resolves before redirecting. -->
    <div v-if="templateAutoLaunching" class="ms-toast ms-toast-info">
      <span class="ms-toast-dot" aria-hidden>◇</span>
      <span>{{ $tr('Loading template — redirecting…', '正在加载模板 — 即将跳转…') }}</span>
    </div>
    <div v-if="templateAutoLaunchError" class="ms-toast ms-toast-error">
      <span>⚠ {{ templateAutoLaunchError }}</span>
      <button class="ms-toast-close" @click="templateAutoLaunchError = ''" aria-label="Close">×</button>
    </div>

    <!-- Document preview modal -->
    <Teleport to="body">
      <div v-if="previewDoc" class="ms-modal-overlay" @click.self="previewDoc = null">
        <div class="ms-modal">
          <div class="ms-modal-header">
            <div class="ms-modal-title">
              <span class="ms-modal-icon" aria-hidden>◈</span>
              <span>{{ previewDoc.title }}</span>
            </div>
            <button class="ms-modal-close" @click="previewDoc = null" aria-label="Close">✕</button>
          </div>
          <div class="ms-modal-meta">
            {{ previewDoc.char_count.toLocaleString() }} {{ $tr('chars', '字符') }}
            <span v-if="previewDoc.url" class="ms-modal-sep">·</span>
            <span v-if="previewDoc.url" class="ms-modal-url">{{ previewDoc.url }}</span>
          </div>
          <pre class="ms-modal-body">{{ previewDoc.text }}</pre>
        </div>
      </div>
    </Teleport>

    <main class="ms-main">
      <!-- ── HERO ── -->
      <section class="ms-hero">
        <span class="ms-chip">{{ $tr('Universal Swarm Intelligence Engine', '通用群体智能引擎') }}</span>

        <div class="ms-hero-stage">
          <div class="ms-shark-wrap ms-float">
            <img src="/shark.webp" alt="MiroShark" class="ms-shark" />
          </div>

          <h1
            class="ms-chrome-text ms-display"
            :data-text="$tr('Simulate anything for $1', '一切皆可模拟 只需 $1')"
          >
            {{ $tr('Simulate anything for $1', '一切皆可模拟 只需 $1') }}
          </h1>
        </div>

        <p class="ms-hero-desc" v-if="!$isZh()">
          Drop in anything — a press release, a news headline, a policy draft, a
          question you can't answer, a historical what-if — and
          <span class="ms-hero-strong">MiroShark</span> spawns
          <span class="ms-hero-accent">hundreds of agents</span> that react to it
          hour by hour. Posting, arguing, trading, changing their minds.
        </p>
        <p class="ms-hero-desc" v-else>
          放入任何素材 — 新闻稿、头条、政策草案、一个无解的问题、一段历史假设 —
          <span class="ms-hero-strong">MiroShark</span>
          会派出<span class="ms-hero-accent">数百个智能体</span>,每小时一轮地做出反应。发帖、辩论、交易、改变想法。
        </p>

        <p class="ms-slogan">
          {{ $tr("Don't predict the future. Simulate it", '不要预测未来。模拟它') }}<span class="ms-cursor">_</span>
        </p>

        <button class="ms-scroll-btn" @click="scrollToBottom" aria-label="Scroll to console">↓</button>
      </section>

      <div class="ms-rule" aria-hidden></div>

      <!-- ── DASHBOARD ── -->
      <section class="ms-dashboard">
        <!-- LEFT: Status + what it does -->
        <aside class="ms-side">
          <div class="ms-side-panel ms-glossy">
            <header class="ms-side-head">
              <span class="ms-status-dot" aria-hidden></span>
              {{ $tr('System Status', '系统状态') }}
            </header>

            <h2 class="ms-side-status">{{ $tr('Ready', '就绪') }}</h2>
            <p class="ms-side-desc">
              {{ $tr('First simulation in ~10 min, ~$1 on the cloud preset. Drop in a doc or pick a trending headline to start.', '使用云端预设,首次模拟约 10 分钟、约 $1。投入一份文档或挑一条热门头条即可开始。') }}
            </p>
          </div>

          <div class="ms-side-panel ms-glossy">
            <header class="ms-side-head ms-side-head-faint">
              <span class="ms-diamond" aria-hidden>◇</span>
              {{ $tr('What it does', '它做什么') }}
            </header>

            <ol class="ms-steps">
              <li class="ms-step" v-for="step in steps" :key="step.num">
                <span class="ms-step-num">{{ step.num }}</span>
                <div>
                  <div class="ms-step-title">{{ $tr(step.titleEn, step.titleZh) }}</div>
                  <div class="ms-step-desc">{{ $tr(step.descEn, step.descZh) }}</div>
                </div>
              </li>
            </ol>
          </div>
        </aside>

        <!-- RIGHT: Console -->
        <section class="ms-console-wrap">
          <!-- Pre-fill banner -->
          <div v-if="prefillBannerVisible" class="ms-prefill" role="status">
            <span class="ms-prefill-icon" aria-hidden>🔗</span>
            <span class="ms-prefill-text">{{ prefillBannerCopy }}</span>
            <button class="ms-prefill-close" :title="$tr('Dismiss', '关闭')" @click="dismissPrefillBanner" aria-label="Dismiss">×</button>
          </div>

          <div class="ms-console ms-glossy">
            <!-- 01 — Files -->
            <section class="ms-block">
              <header class="ms-block-head">
                <span class="ms-block-label">{{ $tr('01 · Reality Seeds', '01 · 现实种子') }}</span>
                <span class="ms-block-meta">{{ $tr('PDF · MD · TXT', 'PDF · MD · TXT') }}</span>
              </header>

              <div
                class="ms-drop"
                :class="{ 'is-over': isDragOver, 'has-files': files.length > 0 }"
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
                  style="display:none"
                  :disabled="loading"
                />
                <div v-if="files.length === 0" class="ms-drop-empty">
                  <div class="ms-drop-arrow" aria-hidden>↑</div>
                  <div class="ms-drop-title">{{ $tr('Drop files to upload', '拖入文件以上传') }}</div>
                  <div class="ms-drop-hint">{{ $tr('or click to browse the file system', '或点击浏览文件系统') }}</div>
                </div>
                <ul v-else class="ms-file-list">
                  <li v-for="(file, i) in files" :key="i" class="ms-file">
                    <span class="ms-file-icon" aria-hidden>📄</span>
                    <span class="ms-file-name">{{ file.name }}</span>
                    <button @click.stop="removeFile(i)" class="ms-x" aria-label="Remove">×</button>
                  </li>
                </ul>
              </div>
            </section>

            <!-- 01a — Ask -->
            <section class="ms-block">
              <header class="ms-block-head">
                <span class="ms-block-label">{{ $tr('01a · Just Ask', '01a · 直接提问') }}</span>
                <span class="ms-block-meta">{{ $tr('No document? Type a question, we synthesize a briefing.', '没有文档?输入一个问题,我们会合成一份简报。') }}</span>
              </header>

              <div class="ms-input-row">
                <input
                  v-model="askQuestion"
                  class="ms-input"
                  type="text"
                  :placeholder="$tr(`e.g. Will the EU AI Act's biometrics clause survive the final trilogue?`, '例如:欧盟人工智能法案的生物识别条款能否在最终三方会议中存活?')"
                  :disabled="loading || askBusy"
                  @keydown.enter.prevent="runAskMode"
                />
                <button class="ms-btn ms-btn-ghost" @click="runAskMode" :disabled="!askQuestion.trim() || loading || askBusy">
                  <span v-if="askBusy">…</span>
                  <span v-else>{{ $tr('Research →', '研究 →') }}</span>
                </button>
              </div>
              <p v-if="askError" class="ms-error">{{ askError }}</p>
              <p v-if="askBusy" class="ms-hint">{{ $tr('Synthesizing briefing — Smart model, ~20–30s.', '正在合成简报 — Smart 模型,大约 20–30 秒。') }}</p>

              <ul v-if="askDocs.length" class="ms-doc-list">
                <li
                  v-for="doc in askDocs"
                  :key="doc.url"
                  class="ms-doc"
                  role="button"
                  tabindex="0"
                  :title="$tr('Click to preview the generated briefing', '点击预览生成的简报')"
                  @click="previewDoc = doc"
                  @keydown.enter.prevent="previewDoc = doc"
                  @keydown.space.prevent="previewDoc = doc"
                >
                  <span class="ms-doc-icon" aria-hidden>◈</span>
                  <div class="ms-doc-info">
                    <div class="ms-doc-title">{{ truncate(doc.title, 70) }}</div>
                    <div class="ms-doc-meta">{{ doc.char_count.toLocaleString() }} {{ $tr('chars', '字符') }} · {{ truncate(doc.url, 72) }}</div>
                  </div>
                  <button @click.stop="removeUrlDocByRef(doc)" class="ms-x" aria-label="Remove">×</button>
                </li>
              </ul>
            </section>

            <!-- 01b — URL -->
            <section class="ms-block">
              <header class="ms-block-head">
                <span class="ms-block-label">{{ $tr('01b · URL Import', '01b · 网址导入') }}</span>
                <span class="ms-block-meta">{{ $tr('Paste article or report URL', '粘贴文章或报告网址') }}</span>
              </header>

              <div class="ms-input-row">
                <input
                  v-model="urlInput"
                  class="ms-input"
                  type="url"
                  placeholder="https://example.com/article"
                  :disabled="loading || urlFetching"
                  @keydown.enter.prevent="fetchUrlDoc"
                />
                <button class="ms-btn ms-btn-ghost" @click="fetchUrlDoc" :disabled="!urlInput.trim() || loading || urlFetching">
                  <span v-if="urlFetching">…</span>
                  <span v-else>{{ $tr('Fetch →', '抓取 →') }}</span>
                </button>
              </div>
              <p v-if="urlError" class="ms-error">{{ urlError }}</p>

              <ul v-if="fetchedDocs.length" class="ms-doc-list">
                <li
                  v-for="doc in fetchedDocs"
                  :key="doc.url"
                  class="ms-doc"
                  role="button"
                  tabindex="0"
                  :title="$tr('Click to preview the extracted content', '点击预览提取的内容')"
                  @click="previewDoc = doc"
                  @keydown.enter.prevent="previewDoc = doc"
                  @keydown.space.prevent="previewDoc = doc"
                >
                  <span class="ms-doc-icon" aria-hidden>◈</span>
                  <div class="ms-doc-info">
                    <div class="ms-doc-title">{{ truncate(doc.title, 70) }}</div>
                    <div class="ms-doc-meta">{{ doc.char_count.toLocaleString() }} {{ $tr('chars', '字符') }} · {{ truncate(doc.url, 72) }}</div>
                  </div>
                  <button @click.stop="removeUrlDocByRef(doc)" class="ms-x" aria-label="Remove">×</button>
                </li>
              </ul>

              <TrendingTopics :busy="urlFetching" @select="handleTrendingSelect" />
            </section>

            <div class="ms-divider"><span>{{ $tr('Input parameters', '输入参数') }}</span></div>

            <!-- 02 — Prompt -->
            <section class="ms-block">
              <header class="ms-block-head">
                <span class="ms-block-label">{{ $tr('>_ 02 · Simulation Prompt', '>_ 02 · 模拟提示词') }}</span>
              </header>

              <ScenarioSuggestions
                :text-preview="scenarioSuggestPreview"
                :simulation-prompt="formData.simulationRequirement"
                @use="handleSuggestionUse"
              />

              <div class="ms-textarea-wrap">
                <textarea
                  v-model="formData.simulationRequirement"
                  class="ms-textarea"
                  :placeholder="$tr('// Enter your simulation requirements in natural language (e.g., If a university announces the revocation of a disciplinary action against a student, what public opinion trends will emerge?)', '// 用自然语言描述你的模拟需求(例如:如果一所大学宣布撤销对一名学生的纪律处分,会出现哪些舆论走向?)')"
                  rows="6"
                  :disabled="loading"
                ></textarea>
                <div class="ms-engine-tag">{{ $tr('Engine: MiroShark-V1.0', '引擎:MiroShark-V1.0') }}</div>
              </div>

              <div v-if="canShareScenarioLink" class="ms-share-row">
                <button
                  class="ms-share-btn"
                  :class="{ 'is-copied': shareLinkCopied }"
                  :title="$tr('Copy a URL that drops a reader into this pre-filled form', '复制可让读者直接进入此预填表单的链接')"
                  @click="copyScenarioShareLink"
                >
                  <span aria-hidden>🔗</span>
                  <span v-if="shareLinkCopied">✓ {{ $tr('Link copied', '链接已复制') }}</span>
                  <span v-else>{{ $tr('Share as link', '分享为链接') }}</span>
                </button>
                <span class="ms-share-hint">
                  {{ $tr('Tweet this URL to invite anyone to run the same setup.', '发推此 URL,即可邀请他人运行相同设置。') }}
                </span>
              </div>
              <p v-if="shareLinkError" class="ms-error">{{ shareLinkError }}</p>
            </section>

            <!-- Launch -->
            <div class="ms-launch">
              <button
                class="ms-cta"
                @click="startSimulation"
                :disabled="!canSubmit || loading"
              >
                <span v-if="!loading">{{ $tr('Launch Simulation', '启动模拟') }}</span>
                <span v-else>{{ $tr('Initializing…', '初始化中…') }}</span>
                <span class="ms-cta-arrow" aria-hidden>→</span>
              </button>
            </div>
          </div>
        </section>
      </section>

      <section class="ms-section"><TemplateGallery /></section>
      <section class="ms-section"><HistoryDatabase /></section>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import TemplateGallery from '../components/TemplateGallery.vue'
import SettingsPanel from '../components/SettingsPanel.vue'
import ScenarioSuggestions from '../components/ScenarioSuggestions.vue'
import TrendingTopics from '../components/TrendingTopics.vue'
import LocaleToggle from '../components/LocaleToggle.vue'
import { fetchUrl } from '../api/graph'
import { askMode } from '../api/simulation'
import { getTemplate } from '../api/templates'
import { setPendingTemplate } from '../store/pendingUpload'
import {
  readPrefilledParams,
  hasAnyPrefill,
  buildScenarioShareUrl,
} from '../utils/urlParams'
import { tr } from '../i18n'

const settingsOpen = ref(false)
const previewDoc = ref(null)

const router = useRouter()
const route = useRoute()

const prefillBannerVisible = ref(false)
const prefillBannerKind = ref('text')

const shareLinkCopiedAt = ref(0)
const shareLinkCopiedTick = ref(0)
const shareLinkError = ref('')

const templateAutoLaunching = ref(false)
const templateAutoLaunchError = ref('')

const formData = ref({ simulationRequirement: '' })
const files = ref([])
const urlInput = ref('')
const urlDocs = ref([])
const urlFetching = ref(false)
const urlError = ref('')
const askQuestion = ref('')
const askBusy = ref(false)
const askError = ref('')
const loading = ref(false)
const error = ref('')
const isDragOver = ref(false)
const fileInput = ref(null)

const steps = [
  { num: '01', titleEn: 'You bring a scenario', titleZh: '你提供一个情景',
    descEn: 'MiroShark builds the world around it — extracts actors, stakes, and open questions from your input.',
    descZh: 'MiroShark 围绕它构建世界 — 从你的输入中提取角色、利害关系与待解问题。' },
  { num: '02', titleEn: 'Hundreds of grounded agents', titleZh: '数百个有据可依的智能体',
    descEn: 'React on Twitter, Reddit, and a prediction market. Hour by hour, round after round.',
    descZh: '在 Twitter、Reddit 与预测市场上做出反应。每小时一轮,一轮接一轮。' },
  { num: '03', titleEn: 'Steer the timeline', titleZh: '掌舵时间线',
    descEn: 'Chat with any agent. Drop breaking news mid-run. Fork a counterfactual and watch it diverge.',
    descZh: '与任意智能体对话。在运行中投入突发新闻。派生一个反事实分支并观察其偏离。' },
  { num: '04', titleEn: 'Get a report', titleZh: '生成报告',
    descEn: 'A Substack-style write-up of what happened, citing actual posts and trades from the run.',
    descZh: 'Substack 风格的复盘文章,引用本次运行中的真实发帖与交易。' },
]

const canSubmit = computed(() => {
  return formData.value.simulationRequirement.trim() !== '' &&
    (files.value.length > 0 || urlDocs.value.length > 0)
})

const triggerFileInput = () => {
  if (!loading.value) fileInput.value?.click()
}

const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

const handleDragOver = () => { if (!loading.value) isDragOver.value = true }
const handleDragLeave = () => { isDragOver.value = false }
const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  addFiles(Array.from(e.dataTransfer.files))
}

const filePreviewText = ref('')

const refreshFilePreviewText = async () => {
  const textish = files.value.filter(f => {
    const ext = (f.name.split('.').pop() || '').toLowerCase()
    return ext === 'md' || ext === 'txt'
  })
  if (textish.length === 0) { filePreviewText.value = ''; return }
  try {
    const chunks = await Promise.all(textish.map(async (f) => {
      try {
        const slice = f.slice ? f.slice(0, 6000) : f
        const txt = await slice.text()
        return (txt || '').slice(0, 3000)
      } catch (_) { return '' }
    }))
    filePreviewText.value = chunks.filter(Boolean).join('\n\n').slice(0, 6000)
  } catch (_) { filePreviewText.value = '' }
}

const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt'].includes(ext)
  })
  files.value.push(...validFiles)
  refreshFilePreviewText()
}

const removeFile = (index) => {
  files.value.splice(index, 1)
  refreshFilePreviewText()
}

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

const handleSuggestionUse = ({ question }) => {
  if (!question) return
  formData.value.simulationRequirement = question
}

const scrollToBottom = () => {
  window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
}

const fetchUrlDoc = async () => {
  const url = urlInput.value.trim()
  if (!url || urlFetching.value) return
  if (urlDocs.value.some(d => d.url === url)) {
    urlError.value = tr('This URL has already been added.', '此网址已添加过。')
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
      urlError.value = res.error || tr('Failed to fetch URL.', '抓取网址失败。')
    }
  } catch (err) {
    urlError.value = err.message || tr('Failed to fetch URL.', '抓取网址失败。')
  } finally {
    urlFetching.value = false
  }
}

const runAskMode = async () => {
  const q = askQuestion.value.trim()
  if (!q || askBusy.value) return
  askBusy.value = true
  askError.value = ''
  try {
    const res = await askMode(q)
    if (!res.success) {
      askError.value = res.error || tr('Ask mode failed.', '提问模式失败。')
      return
    }
    const d = res.data
    const synthUrl = `miroshark://ask/${encodeURIComponent(q.slice(0, 64))}`
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
    askError.value = err?.response?.data?.error || err?.message || tr('Ask mode failed.', '提问模式失败。')
  } finally {
    askBusy.value = false
  }
}

const handleTrendingSelect = ({ url }) => {
  if (!url || urlFetching.value) return
  if (urlDocs.value.some(d => d.url === url)) {
    urlError.value = tr('This URL is already loaded.', '此网址已加载。')
    return
  }
  urlInput.value = url
  urlError.value = ''
  fetchUrlDoc()
}

const removeUrlDocByRef = (doc) => {
  const idx = urlDocs.value.indexOf(doc)
  if (idx >= 0) urlDocs.value.splice(idx, 1)
}

const truncate = (s, max) => {
  if (!s) return ''
  return s.length > max ? s.slice(0, max - 1).trimEnd() + '…' : s
}

const askDocs = computed(() =>
  urlDocs.value.filter(d => typeof d.url === 'string' && d.url.startsWith('miroshark://ask/'))
)
const fetchedDocs = computed(() =>
  urlDocs.value.filter(d => !(typeof d.url === 'string' && d.url.startsWith('miroshark://ask/')))
)

const startSimulation = () => {
  if (!canSubmit.value || loading.value) return
  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(files.value, formData.value.simulationRequirement, urlDocs.value)
    router.push({ name: 'Process', params: { projectId: 'new' } })
  })
}

const dismissPrefillBanner = () => { prefillBannerVisible.value = false }

const prefillBannerCopy = computed(() => {
  switch (prefillBannerKind.value) {
    case 'url':
      return tr(
        'Document pre-filled from a shared link — review the scenario below before launching.',
        '已通过分享链接预填文档 — 启动前请检查下方情景设置。',
      )
    case 'ask':
      return tr(
        'Question pre-filled from a shared link — click Research to synthesize the briefing, or edit the question first.',
        '已通过分享链接预填问题 — 点击「研究」合成简报,或先修改问题。',
      )
    case 'mixed':
      return tr(
        'Scenario, document, and question pre-filled from a shared link — review the form below before launching.',
        '情景、文档与问题均已通过分享链接预填 — 启动前请检查下方表单。',
      )
    default:
      return tr(
        'Scenario pre-filled from a shared link — review the form below before launching.',
        '已通过分享链接预填情景 — 启动前请检查下方表单。',
      )
  }
})

const autoLaunchTemplate = async (slug) => {
  templateAutoLaunching.value = true
  templateAutoLaunchError.value = ''
  try {
    const res = await getTemplate(slug)
    if (!res?.success || !res.data) {
      templateAutoLaunchError.value = tr(
        `Couldn't load that template. The link may be stale.`,
        '无法加载该模板。链接可能已失效。',
      )
      return
    }
    const full = res.data
    setPendingTemplate(
      full.simulation_requirement,
      full.seed_document,
      full.name,
    )
    router.push({ name: 'Process', params: { projectId: 'new' } })
  } catch (err) {
    templateAutoLaunchError.value =
      err?.response?.data?.error ||
      err?.message ||
      tr(
        `Couldn't load that template. The link may be stale.`,
        '无法加载该模板。链接可能已失效。',
      )
  } finally {
    templateAutoLaunching.value = false
  }
}

const applyPrefilledParams = async () => {
  const params = readPrefilledParams(route.query || {})
  if (!hasAnyPrefill(params)) return
  router.replace({ path: '/', query: {} })
  if (params.template) { autoLaunchTemplate(params.template); return }
  let touched = []
  if (params.scenario && !formData.value.simulationRequirement) {
    formData.value.simulationRequirement = params.scenario
    touched.push('scenario')
  }
  if (params.ask && !askQuestion.value) {
    askQuestion.value = params.ask
    touched.push('ask')
  }
  if (params.url) {
    const dup = urlDocs.value.some((d) => d.url === params.url)
    if (!dup) {
      urlInput.value = params.url
      await nextTick()
      fetchUrlDoc()
      touched.push('url')
    }
  }
  if (touched.length === 0) return
  if (touched.length >= 2) prefillBannerKind.value = 'mixed'
  else if (touched[0] === 'url') prefillBannerKind.value = 'url'
  else if (touched[0] === 'ask') prefillBannerKind.value = 'ask'
  else prefillBannerKind.value = 'text'
  prefillBannerVisible.value = true
}

onMounted(() => { applyPrefilledParams() })

const canShareScenarioLink = computed(() => {
  return Boolean(
    formData.value.simulationRequirement.trim() ||
      urlDocs.value.length > 0 ||
      askQuestion.value.trim(),
  )
})

const buildLiveShareUrl = () => {
  const firstHttpDoc = urlDocs.value.find(
    (d) => typeof d.url === 'string' && /^https?:\/\//i.test(d.url),
  )
  return buildScenarioShareUrl({
    scenario: formData.value.simulationRequirement,
    url: firstHttpDoc ? firstHttpDoc.url : '',
    ask: askQuestion.value,
  })
}

const shareLinkCopied = computed(() => {
  void shareLinkCopiedTick.value
  return shareLinkCopiedAt.value > 0 && Date.now() - shareLinkCopiedAt.value < 2200
})

const copyScenarioShareLink = async () => {
  shareLinkError.value = ''
  if (!canShareScenarioLink.value) return
  const url = buildLiveShareUrl()
  try {
    await navigator.clipboard.writeText(url)
    shareLinkCopiedAt.value = Date.now()
    setTimeout(() => { shareLinkCopiedTick.value++ }, 2300)
  } catch (err) {
    shareLinkError.value =
      err?.message || tr('Copy failed — long-press the link to copy manually.', '复制失败 — 长按链接手动复制。')
  }
}
</script>

<style scoped>
/* ═══════════════════════════════════════════════════════════
   HOME — Real MiroShark visual language
   Deep space + chrome + glossy violet panels.
   Scoped: only this view is dark. The rest of the app keeps
   its existing theme until the next pass.
   ═══════════════════════════════════════════════════════════ */

.ms-home {
  position: relative;
  min-height: 100vh;
  color: #f4f1ff;
  font-family: 'Geist', system-ui, -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased;
  overflow-x: clip;
  /* Solid dark base so the whole page reads dark even where the
     fixed gradients tile below the fold. The radial-gradient layers
     stack on top via .ms-space-bg. */
  background:
    radial-gradient(ellipse 60% 50% at 20% 110%, rgba(56, 30, 110, 0.35), transparent 70%),
    radial-gradient(ellipse 60% 50% at 80% 130%, rgba(150, 80, 230, 0.2), transparent 70%),
    linear-gradient(180deg, #050210 0%, #0a0420 45%, #06021a 80%, #02010a 100%);
}

/* Hero halo — fixed so it stays glued to the top while you scroll. */
.ms-space-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    radial-gradient(ellipse 55% 45% at 50% 25%, rgba(139, 92, 246, 0.55), transparent 65%),
    radial-gradient(ellipse 70% 50% at 50% 50%, rgba(76, 29, 149, 0.35), transparent 70%),
    radial-gradient(ellipse 35% 30% at 85% 20%, rgba(150, 80, 230, 0.35), transparent 70%);
  mix-blend-mode: screen;
  opacity: 0.9;
}

.ms-space-stars {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background-image:
    radial-gradient(1px 1px at 12% 18%, rgba(255,255,255,1), transparent 50%),
    radial-gradient(1px 1px at 78% 9%, rgba(255,255,255,0.9), transparent 50%),
    radial-gradient(1.5px 1.5px at 33% 72%, rgba(255,255,255,1), transparent 50%),
    radial-gradient(1px 1px at 62% 38%, rgba(220,220,255,0.85), transparent 50%),
    radial-gradient(1px 1px at 88% 56%, rgba(255,255,255,0.95), transparent 50%),
    radial-gradient(1.5px 1.5px at 22% 88%, rgba(255,240,255,0.75), transparent 50%),
    radial-gradient(1px 1px at 7% 42%, rgba(255,255,255,0.65), transparent 50%),
    radial-gradient(1px 1px at 49% 14%, rgba(255,255,255,1), transparent 50%),
    radial-gradient(1px 1px at 92% 82%, rgba(255,255,255,0.75), transparent 50%),
    radial-gradient(1.5px 1.5px at 41% 51%, rgba(255,255,255,0.65), transparent 50%),
    radial-gradient(1px 1px at 67% 91%, rgba(220,220,255,0.75), transparent 50%),
    radial-gradient(1px 1px at 17% 63%, rgba(255,255,255,0.65), transparent 50%),
    radial-gradient(1px 1px at 55% 78%, rgba(255,255,255,0.8), transparent 50%),
    radial-gradient(1px 1px at 73% 24%, rgba(255,255,255,0.7), transparent 50%);
  animation: ms-twinkle 6s ease-in-out infinite alternate;
}

@keyframes ms-twinkle { from { opacity: 0.55 } to { opacity: 1 } }

/* All page content sits above the fixed bg/stars layers. */
.ms-nav, .ms-main { position: relative; z-index: 1; }

/* ── Top Nav ── */
.ms-nav {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.85rem 1.5rem;
  background: linear-gradient(180deg, rgba(10,5,26,0.85) 0%, rgba(5,3,10,0.6) 70%, transparent 100%);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}
@media (min-width: 640px) { .ms-nav { padding: 1rem 2rem } }

.ms-brand {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  color: #f4f1ff;
  text-decoration: none;
  font-weight: 700;
  letter-spacing: -0.01em;
  font-size: 1.05rem;
}
.ms-brand-mark {
  width: 22px;
  height: 22px;
  object-fit: contain;
  filter: drop-shadow(0 4px 10px rgba(167, 139, 250, 0.5));
}

.ms-nav-links { display: flex; align-items: center; gap: 0.5rem; }

.ms-nav-link, .ms-nav-icon {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  height: 36px;
  padding: 0 0.9rem;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 9999px;
  color: #ece8ff;
  font-size: 0.82rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-decoration: none;
  background: linear-gradient(180deg, rgba(70,55,120,0.45) 0%, rgba(20,14,42,0.7) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.2),
    inset 0 -1px 0 rgba(0,0,0,0.4),
    0 8px 22px -10px rgba(139,92,246,0.4);
  transition: border-color 180ms ease, transform 180ms ease, color 180ms ease;
  cursor: pointer;
  font-family: inherit;
}
.ms-nav-icon {
  width: 36px;
  padding: 0;
  gap: 0;
  justify-content: center;
  font-size: 1.05rem;
  line-height: 1;
}
.ms-nav-link:hover, .ms-nav-icon:hover {
  border-color: rgba(167,139,250,0.55);
  color: #ffffff;
  transform: translateY(-1px);
}
.ms-nav-arrow { opacity: 0.7; }

/* ── Hero ── */
.ms-main { max-width: 1180px; margin: 0 auto; padding: 0 1.25rem 5rem; }
@media (min-width: 640px) { .ms-main { padding: 0 2rem 6rem } }

.ms-hero {
  position: relative;
  text-align: center;
  padding: 5rem 0 4rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.5rem;
}
@media (min-width: 1024px) { .ms-hero { padding: 7rem 0 5rem } }

.ms-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  height: 32px;
  padding: 0 0.95rem;
  border-radius: 9999px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: #e9e6ff;
  background: linear-gradient(180deg, rgba(80,60,140,0.5) 0%, rgba(28,18,58,0.7) 100%);
  box-shadow:
    0 0 0 1px rgba(255,255,255,0.1),
    inset 0 1px 0 rgba(255,255,255,0.25),
    inset 0 -1px 0 rgba(0,0,0,0.4),
    0 8px 24px -8px rgba(139,92,246,0.4);
  text-shadow: 0 1px 0 rgba(0,0,0,0.4);
}
.ms-chip::before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 9999px;
  background: radial-gradient(circle at 30% 30%, #fff 0%, #a78bfa 60%, #4c1d95 100%);
  box-shadow: 0 0 8px rgba(167,139,250,0.9), 0 0 16px rgba(139,92,246,0.6);
}

.ms-hero-stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1.25rem;
  margin-top: 0.5rem;
  width: 100%;
}
@media (min-width: 900px) {
  .ms-hero-stage { flex-direction: row; gap: 2.5rem; }
}

.ms-shark-wrap {
  position: relative;
  width: 150px;
  height: 160px;
  flex-shrink: 0;
}
@media (min-width: 900px) { .ms-shark-wrap { width: 200px; height: 215px } }

.ms-shark {
  width: 100%;
  height: 100%;
  object-fit: contain;
  filter:
    drop-shadow(0 30px 60px rgba(139,92,246,0.45))
    drop-shadow(0 10px 24px rgba(0,0,0,0.7))
    drop-shadow(0 0 80px rgba(167,139,250,0.35));
}

.ms-float { animation: ms-float 6s ease-in-out infinite; }
@keyframes ms-float {
  0%, 100% { transform: translateY(0) }
  50%      { transform: translateY(-10px) }
}

.ms-display {
  font-size: clamp(2.5rem, 6.5vw, 5.5rem);
  line-height: 1.02;
  font-weight: 900;
  letter-spacing: -0.04em;
  margin: 0;
  text-align: center;
}

.ms-chrome-text {
  background: linear-gradient(
    180deg,
    #ffffff 0%, #e9e9f5 15%, #b9b9cc 32%, #6e6e85 50%,
    #c8c8dc 68%, #ffffff 85%, #d6d6e8 100%
  );
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-stroke: 1px rgba(255,255,255,0.15);
  filter:
    drop-shadow(0 1px 0 rgba(255,255,255,0.4))
    drop-shadow(0 4px 12px rgba(167,139,250,0.35))
    drop-shadow(0 16px 32px rgba(0,0,0,0.6));
  position: relative;
}
.ms-chrome-text::after {
  content: attr(data-text);
  position: absolute;
  inset: 0;
  background: linear-gradient(100deg, transparent 30%, rgba(255,255,255,0.85) 50%, transparent 70%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  background-size: 200% 100%;
  animation: ms-shimmer 5s linear infinite;
  mix-blend-mode: screen;
  pointer-events: none;
}
@keyframes ms-shimmer {
  0% { background-position: 200% 0 }
  100% { background-position: -100% 0 }
}

.ms-hero-desc {
  max-width: 700px;
  font-size: 1.05rem;
  line-height: 1.6;
  color: rgba(244,241,255,0.85);
  margin: 0 auto;
}
.ms-hero-strong { color: #ffffff; font-weight: 700; }
.ms-hero-accent { color: #c4b5fd; font-weight: 600; }

.ms-slogan {
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 0.95rem;
  letter-spacing: 0.04em;
  color: rgba(228,222,255,0.7);
  margin-top: 0.5rem;
}
.ms-cursor {
  display: inline-block;
  margin-left: 2px;
  animation: ms-blink 1s steps(2) infinite;
}
@keyframes ms-blink { 50% { opacity: 0 } }

.ms-scroll-btn {
  margin-top: 0.5rem;
  width: 44px;
  height: 44px;
  border-radius: 9999px;
  color: #f4f1ff;
  background: linear-gradient(180deg, #4a4360 0%, #2a2440 45%, #18132a 55%, #3a3450 100%);
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.4),
    inset 0 -1px 0 rgba(0,0,0,0.6),
    0 10px 24px -8px rgba(0,0,0,0.8);
  font-size: 1.1rem;
  cursor: pointer;
  transition: transform 180ms ease, box-shadow 180ms ease;
}
.ms-scroll-btn:hover {
  transform: translateY(-2px);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.5),
    inset 0 -1px 0 rgba(0,0,0,0.6),
    0 16px 32px -8px rgba(139,92,246,0.5);
}

.ms-rule {
  height: 1px;
  margin: 0 auto;
  max-width: 720px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(167,139,250,0.4) 20%,
    rgba(255,255,255,0.5) 50%,
    rgba(167,139,250,0.4) 80%,
    transparent 100%
  );
  box-shadow: 0 0 16px rgba(167,139,250,0.3);
}

/* ── Toasts ── */
.ms-toast {
  position: fixed;
  top: 5.5rem;
  left: 50%;
  transform: translateX(-50%);
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.65rem 1rem;
  border-radius: 9999px;
  font-size: 0.85rem;
  font-weight: 500;
  z-index: 50;
  color: #f4f1ff;
  background: linear-gradient(180deg, rgba(40,30,70,0.85) 0%, rgba(18,12,38,0.92) 100%);
  border: 1px solid rgba(167,139,250,0.35);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow: 0 16px 40px -16px rgba(0,0,0,0.8);
}
.ms-toast-error { border-color: rgba(240,171,252,0.5); }
.ms-toast-dot { color: #a78bfa; }
.ms-toast-close {
  margin-left: 0.25rem;
  background: transparent;
  border: none;
  color: inherit;
  font-size: 1rem;
  cursor: pointer;
  opacity: 0.7;
}
.ms-toast-close:hover { opacity: 1; }

/* ── Modal ── */
.ms-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(5, 3, 10, 0.7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
.ms-modal {
  width: 100%;
  max-width: 760px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  border-radius: 1.25rem;
  background: linear-gradient(180deg, rgba(40,30,70,0.95) 0%, rgba(18,12,38,0.97) 100%);
  border: 1px solid rgba(167,139,250,0.3);
  box-shadow: 0 30px 80px -20px rgba(0,0,0,0.9);
  color: #f4f1ff;
  overflow: hidden;
}
.ms-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid rgba(167,139,250,0.18);
}
.ms-modal-title { display: inline-flex; align-items: center; gap: 0.5rem; font-weight: 700; }
.ms-modal-icon { color: #a78bfa; }
.ms-modal-close {
  background: transparent;
  border: none;
  color: rgba(244,241,255,0.7);
  font-size: 1.1rem;
  cursor: pointer;
}
.ms-modal-close:hover { color: #fff; }
.ms-modal-meta {
  padding: 0.6rem 1.25rem;
  font-size: 0.78rem;
  color: rgba(228,222,255,0.6);
  border-bottom: 1px solid rgba(167,139,250,0.12);
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.ms-modal-sep { opacity: 0.5; }
.ms-modal-url {
  font-family: 'Geist Mono', ui-monospace, monospace;
  word-break: break-all;
}
.ms-modal-body {
  padding: 1.25rem;
  overflow: auto;
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 0.82rem;
  line-height: 1.55;
  color: rgba(244,241,255,0.85);
  white-space: pre-wrap;
}

/* ── Dashboard ── */
.ms-dashboard {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1.5rem;
  margin-top: 3rem;
}
@media (min-width: 1024px) {
  .ms-dashboard {
    grid-template-columns: 22rem 1fr;
    gap: 2rem;
    align-items: start;
  }
}

/* Glossy panel base */
.ms-glossy {
  position: relative;
  border-radius: 1.5rem;
  padding: 1.5rem;
  background: linear-gradient(180deg, rgba(40,30,70,0.6) 0%, rgba(18,12,38,0.78) 100%);
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.16),
    inset 0 -1px 0 rgba(0,0,0,0.45),
    0 20px 48px -16px rgba(0,0,0,0.8),
    0 0 60px -20px rgba(139,92,246,0.25);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  overflow: hidden;
  isolation: isolate;
}
.ms-glossy::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(180deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.02) 30%, transparent 60%);
  pointer-events: none;
}
@media (min-width: 640px) { .ms-glossy { padding: 1.75rem } }

/* Left: Status */
.ms-side { display: flex; flex-direction: column; gap: 1.25rem; }
.ms-side-panel { display: flex; flex-direction: column; gap: 0.65rem; }
.ms-side-head {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 0.72rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: rgba(228,222,255,0.7);
}
.ms-side-head-faint { color: rgba(228,222,255,0.55); }
.ms-status-dot {
  width: 9px;
  height: 9px;
  border-radius: 9999px;
  background: radial-gradient(circle at 30% 30%, #fff 0%, #a78bfa 60%, #4c1d95 100%);
  box-shadow: 0 0 8px rgba(167,139,250,0.9), 0 0 16px rgba(139,92,246,0.6);
  animation: ms-pulse 2.4s ease-in-out infinite;
}
@keyframes ms-pulse {
  0%, 100% { opacity: 0.8; transform: scale(1) }
  50%      { opacity: 1; transform: scale(1.15) }
}
.ms-diamond { color: #a78bfa; }

.ms-side-status {
  font-size: 2.5rem;
  font-weight: 900;
  letter-spacing: -0.03em;
  margin: 0.25rem 0 0.5rem;
  background: linear-gradient(180deg, #ffffff 0%, #e2dcf6 55%, #a99fc8 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.ms-side-desc {
  color: rgba(244,241,255,0.78);
  font-size: 0.92rem;
  line-height: 1.55;
}

.ms-steps {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0 0;
  display: flex;
  flex-direction: column;
  gap: 0.95rem;
}
.ms-step {
  display: grid;
  grid-template-columns: 2.25rem 1fr;
  gap: 0.85rem;
  align-items: start;
}
.ms-step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 9999px;
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 0.78rem;
  font-weight: 700;
  color: #e9e6ff;
  background: linear-gradient(180deg, rgba(80,60,140,0.55) 0%, rgba(28,18,58,0.85) 100%);
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.2);
}
.ms-step-title { font-weight: 700; font-size: 0.95rem; color: #f4f1ff; }
.ms-step-desc {
  margin-top: 2px;
  font-size: 0.85rem;
  line-height: 1.55;
  color: rgba(228,222,255,0.7);
}

/* Right: Console */
.ms-console-wrap { display: flex; flex-direction: column; gap: 1rem; }

.ms-prefill {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.85rem 1rem;
  border-radius: 1rem;
  background: linear-gradient(180deg, rgba(70,55,120,0.45) 0%, rgba(28,18,58,0.7) 100%);
  border: 1px solid rgba(167,139,250,0.35);
  color: #ece8ff;
  font-size: 0.88rem;
}
.ms-prefill-icon { font-size: 0.95rem; }
.ms-prefill-text { flex: 1; line-height: 1.4; }
.ms-prefill-close {
  background: transparent;
  border: none;
  color: rgba(244,241,255,0.6);
  font-size: 1.1rem;
  cursor: pointer;
}
.ms-prefill-close:hover { color: #fff; }

.ms-console {
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
}

.ms-block { display: flex; flex-direction: column; gap: 0.65rem; }
.ms-block-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}
.ms-block-label {
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 0.74rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #c4b5fd;
}
.ms-block-meta {
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 0.7rem;
  color: rgba(228,222,255,0.55);
  letter-spacing: 0.04em;
}

/* Drop zone */
.ms-drop {
  position: relative;
  border-radius: 1rem;
  padding: 1.75rem 1.25rem;
  text-align: center;
  border: 1.5px dashed rgba(167,139,250,0.4);
  background: linear-gradient(180deg, rgba(22,16,46,0.4) 0%, rgba(8,5,22,0.65) 100%);
  cursor: pointer;
  transition: border-color 180ms ease, background 180ms ease, transform 180ms ease;
}
.ms-drop:hover, .ms-drop.is-over {
  border-color: rgba(196,181,253,0.85);
  background: linear-gradient(180deg, rgba(48,36,84,0.5) 0%, rgba(20,14,42,0.75) 100%);
  transform: translateY(-1px);
}
.ms-drop.has-files { padding: 1rem; text-align: left; }
.ms-drop-empty { display: flex; flex-direction: column; align-items: center; gap: 0.4rem; }
.ms-drop-arrow { font-size: 1.5rem; color: #a78bfa; filter: drop-shadow(0 4px 12px rgba(167,139,250,0.5)); }
.ms-drop-title { font-size: 1rem; font-weight: 600; color: #f4f1ff; }
.ms-drop-hint { font-size: 0.8rem; color: rgba(228,222,255,0.55); }

.ms-file-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.4rem; }
.ms-file {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.55rem 0.8rem;
  border-radius: 0.65rem;
  background: rgba(40,30,70,0.55);
  border: 1px solid rgba(255,255,255,0.06);
}
.ms-file-name { flex: 1; font-size: 0.88rem; color: #f4f1ff; word-break: break-all; }
.ms-x {
  background: transparent;
  border: none;
  color: rgba(244,241,255,0.55);
  font-size: 1rem;
  cursor: pointer;
  padding: 0 0.25rem;
}
.ms-x:hover { color: #f0abfc; }

/* Inputs */
.ms-input-row { display: flex; gap: 0.5rem; align-items: stretch; }
.ms-input, .ms-textarea {
  flex: 1;
  width: 100%;
  padding: 0.75rem 1rem;
  font-family: inherit;
  font-size: 0.92rem;
  color: #f4f1ff;
  background: linear-gradient(180deg, rgba(22,16,46,0.85) 0%, rgba(8,5,22,0.95) 100%);
  border: 1px solid rgba(167,139,250,0.25);
  border-radius: 0.85rem;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.2s ease;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
}
.ms-input:focus, .ms-textarea:focus {
  border-color: rgba(167,139,250,0.7);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.08),
    0 0 0 4px rgba(139,92,246,0.18);
}
.ms-input::placeholder, .ms-textarea::placeholder { color: rgba(228,222,255,0.4); }
.ms-input { height: 44px; }

.ms-textarea-wrap { position: relative; }
.ms-textarea {
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 0.88rem;
  line-height: 1.55;
  min-height: 140px;
  resize: vertical;
}

.ms-engine-tag {
  position: absolute;
  right: 0.85rem;
  bottom: 0.65rem;
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 0.65rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(228,222,255,0.55);
  padding: 0.2rem 0.55rem;
  border-radius: 0.5rem;
  background: rgba(40,30,70,0.6);
  border: 1px solid rgba(255,255,255,0.06);
  pointer-events: none;
}

/* Buttons */
.ms-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  padding: 0 1.1rem;
  height: 44px;
  border-radius: 0.85rem;
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  cursor: pointer;
  border: none;
  transition: transform 180ms ease, box-shadow 180ms ease, background 180ms ease, opacity 180ms ease;
}
.ms-btn:disabled { opacity: 0.45; cursor: not-allowed; }

.ms-btn-ghost {
  color: #ece8ff;
  background: linear-gradient(180deg, rgba(70,55,120,0.55) 0%, rgba(20,14,42,0.75) 100%);
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.2),
    inset 0 -1px 0 rgba(0,0,0,0.4),
    0 8px 22px -10px rgba(139,92,246,0.45);
}
.ms-btn-ghost:not(:disabled):hover {
  border-color: rgba(167,139,250,0.55);
  transform: translateY(-1px);
}

/* Errors / hints */
.ms-error {
  color: #f0abfc;
  font-size: 0.82rem;
  margin: 0;
}
.ms-hint {
  font-family: 'Geist Mono', ui-monospace, monospace;
  color: rgba(228,222,255,0.6);
  font-size: 0.78rem;
  margin: 0;
}

/* Doc list (fetched URLs / ask briefings) */
.ms-doc-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.5rem; }
.ms-doc {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.7rem 0.9rem;
  border-radius: 0.85rem;
  background: linear-gradient(180deg, rgba(48,36,84,0.55) 0%, rgba(20,14,42,0.7) 100%);
  border: 1px solid rgba(255,255,255,0.06);
  cursor: pointer;
  transition: border-color 180ms ease, transform 180ms ease;
}
.ms-doc:hover { border-color: rgba(167,139,250,0.45); transform: translateY(-1px); }
.ms-doc-icon { color: #a78bfa; }
.ms-doc-info { flex: 1; min-width: 0; }
.ms-doc-title {
  font-size: 0.92rem;
  font-weight: 600;
  color: #f4f1ff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ms-doc-meta {
  margin-top: 2px;
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 0.74rem;
  color: rgba(228,222,255,0.6);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Divider with text */
.ms-divider {
  position: relative;
  text-align: center;
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 0.7rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: rgba(228,222,255,0.5);
}
.ms-divider::before, .ms-divider::after {
  content: "";
  position: absolute;
  top: 50%;
  width: calc(50% - 5rem);
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(167,139,250,0.35), transparent);
}
.ms-divider::before { left: 0; }
.ms-divider::after  { right: 0; }
.ms-divider span { background: transparent; }

/* Share link */
.ms-share-row {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  flex-wrap: wrap;
  margin-top: 0.65rem;
}
.ms-share-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  height: 38px;
  padding: 0 1rem;
  border-radius: 9999px;
  font-family: inherit;
  font-size: 0.82rem;
  font-weight: 600;
  color: #ece8ff;
  background: linear-gradient(180deg, rgba(70,55,120,0.55) 0%, rgba(20,14,42,0.75) 100%);
  border: 1px solid rgba(167,139,250,0.35);
  cursor: pointer;
  transition: border-color 180ms ease, transform 180ms ease, color 180ms ease;
}
.ms-share-btn:hover { border-color: rgba(196,181,253,0.65); color: #fff; transform: translateY(-1px); }
.ms-share-btn.is-copied {
  color: #c4b5fd;
  border-color: rgba(196,181,253,0.65);
  background: linear-gradient(180deg, rgba(80,60,140,0.7) 0%, rgba(28,18,58,0.85) 100%);
}
.ms-share-hint {
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 0.74rem;
  color: rgba(228,222,255,0.55);
  flex: 1;
  min-width: 220px;
}

/* Launch CTA */
.ms-launch { display: flex; justify-content: flex-end; padding-top: 0.5rem; }
.ms-cta {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  height: 56px;
  padding: 0 2rem;
  border-radius: 9999px;
  font-family: inherit;
  font-size: 0.95rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #f8f5ff;
  background: linear-gradient(180deg, #6a4ad6 0%, #4922b8 45%, #2a118a 55%, #4f2dc4 100%);
  border: none;
  cursor: pointer;
  text-shadow: 0 1px 0 rgba(0,0,0,0.4);
  box-shadow:
    0 0 0 1px rgba(255,255,255,0.15),
    inset 0 1px 0 rgba(255,255,255,0.5),
    inset 0 -1px 0 rgba(0,0,0,0.5),
    0 14px 32px -8px rgba(139,92,246,0.6),
    0 0 60px -10px rgba(167,139,250,0.5);
  transition: transform 200ms cubic-bezier(0.2,0.8,0.2,1), box-shadow 200ms ease, background 200ms ease, opacity 200ms ease;
  overflow: hidden;
  isolation: isolate;
}
.ms-cta::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(180deg, rgba(255,255,255,0.4) 0%, rgba(255,255,255,0.08) 40%, transparent 55%);
  pointer-events: none;
}
.ms-cta:not(:disabled):hover {
  transform: translateY(-2px);
  background: linear-gradient(180deg, #7d5ee8 0%, #5728d4 45%, #3414a3 55%, #5e3bde 100%);
  box-shadow:
    0 0 0 1px rgba(255,255,255,0.22),
    inset 0 1px 0 rgba(255,255,255,0.55),
    inset 0 -1px 0 rgba(0,0,0,0.5),
    0 22px 44px -10px rgba(139,92,246,0.75),
    0 0 80px -10px rgba(167,139,250,0.65);
}
.ms-cta:disabled { opacity: 0.5; cursor: not-allowed; }
.ms-cta-arrow { font-size: 1.1rem; }

/* Sub-sections (TemplateGallery / HistoryDatabase) — given a glossy
   wrapper so the inner light styles read as "embedded in a dark frame"
   rather than floating awkwardly. */
.ms-section {
  margin-top: 3rem;
  border-radius: 1.5rem;
  padding: 0.75rem;
  background: linear-gradient(180deg, rgba(20,14,42,0.55) 0%, rgba(8,5,22,0.75) 100%);
  border: 1px solid rgba(167,139,250,0.18);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.06),
    0 20px 48px -16px rgba(0,0,0,0.8);
}

@media (max-width: 1023px) {
  .ms-side { order: 2; }
  .ms-console-wrap { order: 1; }
}
</style>
