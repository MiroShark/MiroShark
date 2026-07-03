<template>
  <div class="ms-home">
    <!-- Deep-space background + star field now live globally in App.vue
         (.space-bg / .space-stars) so every route shares them. -->

    <!-- ── Top Navigation ── -->
    <nav class="ms-nav">
      <router-link to="/" class="ms-brand">
        <img src="/shark.webp" alt="" class="ms-brand-mark" />
        <span>MiroShark</span>
      </router-link>
      <div class="ms-nav-links">
        <router-link to="/explore" class="ms-nav-link" :title="$tr('Browse public simulations', '浏览公开模拟', { de: 'Öffentliche Simulationen durchsuchen', fr: 'Parcourir les simulations publiques' })">
          {{ $tr('Explore', '浏览', { de: 'Entdecken', fr: 'Explorer' }) }}
        </router-link>
        <a href="https://github.com/aaronjmars/MiroShark" target="_blank" rel="noopener" class="ms-nav-link">
          GitHub <span class="ms-nav-arrow">↗</span>
        </a>
        <LocaleToggle />
        <button class="ms-nav-icon" @click="settingsOpen = true" :title="$tr('Settings', '设置', { de: 'Einstellungen', fr: 'Paramètres' })" aria-label="Settings">
          <svg viewBox="0 0 24 24" class="ms-nav-svg" fill="currentColor" aria-hidden="true">
            <path d="M19.4 13a7.8 7.8 0 0 0 0-2l2-1.6-2-3.4-2.4 1a7.6 7.6 0 0 0-1.7-1l-.3-2.5h-4l-.3 2.5a7.6 7.6 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.6a7.8 7.8 0 0 0 0 2l-2 1.6 2 3.4 2.4-1a7.6 7.6 0 0 0 1.7 1l.3 2.5h4l.3-2.5a7.6 7.6 0 0 0 1.7-1l2.4 1 2-3.4-2-1.6ZM12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7Z" />
          </svg>
        </button>
      </div>
    </nav>

    <SettingsPanel :open="settingsOpen" @close="settingsOpen = false" />

    <!-- Template auto-launch toast — visible briefly while a ?template= link
         resolves before redirecting. -->
    <div v-if="templateAutoLaunching" class="ms-toast ms-toast-info">
      <span class="ms-toast-dot" aria-hidden>◇</span>
      <span>{{ $tr('Loading template — redirecting…', '正在加载模板 — 即将跳转…', { de: 'Vorlage wird geladen — Weiterleitung…', fr: 'Chargement du modèle — redirection…' }) }}</span>
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
            {{ previewDoc.char_count.toLocaleString() }} {{ $tr('chars', '字符', { de: 'Zeichen', fr: 'caractères' }) }}
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
        <span class="ms-chip">{{ $tr('Your first result in under 10 minutes', '10 分钟内得到首个结果', { de: 'Dein erstes Ergebnis in unter 10 Minuten', fr: 'Votre premier résultat en moins de 10 minutes' }) }}</span>

        <div class="ms-hero-stage">
          <div class="ms-shark-wrap ms-float">
            <img src="/shark.webp" alt="MiroShark" class="ms-shark" />
          </div>

          <h1
            class="ms-chrome-text ms-display"
            :data-text="$tr('Simulate anything for $1', '一切皆可模拟 只需 $1', { de: 'Alles simulieren für $1', fr: `Simulez n'importe quoi pour $1` })"
          >
            {{ $tr('Simulate anything for $1', '一切皆可模拟 只需 $1', { de: 'Alles simulieren für $1', fr: `Simulez n'importe quoi pour $1` }) }}
          </h1>
        </div>

        <p class="ms-hero-desc" v-if="$isDe()">
          Wirf alles hinein — eine Pressemitteilung, eine Schlagzeile, einen Gesetzesentwurf, eine Frage ohne Antwort, ein historisches Was-wäre-wenn — und
          <span class="ms-hero-strong">MiroShark</span> lässt
          <span class="ms-hero-accent">Hunderte von Agenten</span> entstehen, die Stunde für Stunde darauf reagieren. Posten, streiten, handeln, ihre Meinung ändern.
        </p>
        <p class="ms-hero-desc" v-else-if="$isZh()">
          放入任何素材 — 新闻稿、头条、政策草案、一个无解的问题、一段历史假设 —
          <span class="ms-hero-strong">MiroShark</span>
          会派出<span class="ms-hero-accent">数百个智能体</span>,每小时一轮地做出反应。发帖、辩论、交易、改变想法。
        </p>
        <p class="ms-hero-desc" v-else>
          Drop in anything — a press release, a news headline, a policy draft, a
          question you can't answer, a historical what-if — and
          <span class="ms-hero-strong">MiroShark</span> spawns
          <span class="ms-hero-accent">hundreds of agents</span> that react to it
          hour by hour. Posting, arguing, trading, changing their minds.
        </p>

        <p class="ms-slogan">
          {{ $tr("Don't predict the future. Simulate it", '不要预测未来。模拟它', { de: 'Nicht die Zukunft vorhersagen. Sie simulieren' }) }}<span class="ms-cursor">_</span>
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
              {{ $tr('System Status', '系统状态', { de: 'Systemstatus', fr: 'État du système' }) }}
            </header>

            <h2 class="ms-side-status">{{ $tr('Ready', '就绪', { de: 'Bereit', fr: 'Prêt' }) }}</h2>
            <p class="ms-side-desc">
              {{ $tr('First simulation in ~10 min, ~$1 on the cloud preset. Drop in a doc or pick a trending headline to start.', '使用云端预设,首次模拟约 10 分钟、约 $1。投入一份文档或挑一条热门头条即可开始。', { de: 'Erste Simulation in ~10 Min., ~$1 mit dem Cloud-Preset. Fügen Sie ein Dokument ein oder wählen Sie eine aktuelle Schlagzeile zum Starten.', fr: 'Première simulation en ~10 min, ~$1 sur le preset cloud. Déposez un document ou choisissez un titre tendance pour commencer.' }) }}
            </p>
          </div>

          <div class="ms-side-panel ms-glossy">
            <header class="ms-side-head ms-side-head-faint">
              <span class="ms-diamond" aria-hidden>◇</span>
              {{ $tr('What it does', '它做什么', { de: 'Was es macht', fr: 'Ce que ça fait' }) }}
            </header>

            <ol class="ms-steps">
              <li class="ms-step" v-for="step in steps" :key="step.num">
                <span class="ms-step-num">{{ step.num }}</span>
                <div>
                  <div class="ms-step-title">{{ $tr(step.titleEn, step.titleZh, step.titleDe) }}</div>
                  <div class="ms-step-desc">{{ $tr(step.descEn, step.descZh, step.descDe) }}</div>
                </div>
              </li>
            </ol>
          </div>
        </aside>

        <!-- RIGHT: Console -->
        <section class="ms-console-wrap">
          <!-- Pre-fill banner -->
          <div v-if="prefillBannerVisible" class="ms-prefill" role="status">
            <svg class="ms-prefill-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M3.9 12a3.1 3.1 0 0 1 3.1-3.1h4V7H7a5 5 0 0 0 0 10h4v-1.9H7A3.1 3.1 0 0 1 3.9 12Zm5.1 1h6v-2H9v2Zm8-6h-4v1.9h4a3.1 3.1 0 0 1 0 6.2h-4V17h4a5 5 0 0 0 0-10Z" />
            </svg>
            <span class="ms-prefill-text">{{ prefillBannerCopy }}</span>
            <button class="ms-prefill-close" :title="$tr('Dismiss', '关闭', { de: 'Schließen', fr: 'Ignorer' })" @click="dismissPrefillBanner" aria-label="Dismiss">×</button>
          </div>

          <div class="ms-console ms-glossy">
            <!-- 01 — Files -->
            <section class="ms-block">
              <header class="ms-block-head">
                <span class="ms-block-label">{{ $tr('01 · Reality Seeds', '01 · 现实种子', { de: '01 · Faktenbasis (Seeds)' }) }}</span>
                <span class="ms-block-meta">{{ $tr('PDF · MD · TXT', 'PDF · MD · TXT', { de: 'PDF · MD · TXT' }) }}</span>
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
                  <div class="ms-drop-title">{{ $tr('Drop files to upload', '拖入文件以上传', { de: 'Dateien zum Hochladen ablegen', fr: 'Déposez vos fichiers ici' }) }}</div>
                  <div class="ms-drop-hint">{{ $tr('or click to browse the file system', '或点击浏览文件系统', { de: 'oder klicken zum Durchsuchen', fr: 'ou cliquez pour parcourir vos fichiers' }) }}</div>
                </div>
                <ul v-else class="ms-file-list">
                  <li v-for="(file, i) in files" :key="i" class="ms-file">
                    <svg class="ms-file-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                      <path d="M6 2h8l4 4v16H6V2zm7 1.5V7h3.5L13 3.5z" />
                    </svg>
                    <span class="ms-file-name">{{ file.name }}</span>
                    <button @click.stop="removeFile(i)" class="ms-x" aria-label="Remove">×</button>
                  </li>
                </ul>
              </div>
            </section>

            <!-- 01a — Ask -->
            <section class="ms-block">
              <header class="ms-block-head">
                <span class="ms-block-label">{{ $tr('01a · Just Ask', '01a · 直接提问', { de: '01a · Einfach fragen' }) }}</span>
                <span class="ms-block-meta">{{ $tr('No document? Type a question, we synthesize a briefing.', '没有文档?输入一个问题,我们会合成一份简报。', { de: 'Kein Dokument? Eine Frage eingeben, wir erstellen ein Briefing.', fr: 'Aucun document ? Tapez une question, nous synthétisons un brief.' }) }}</span>
              </header>

              <div class="ms-input-row">
                <input
                  v-model="askQuestion"
                  class="ms-input"
                  type="text"
                  :placeholder="$tr(`e.g. Will the EU AI Act's biometrics clause survive the final trilogue?`, '例如:欧盟人工智能法案的生物识别条款能否在最终三方会议中存活?', { de: 'z. B. Übersteht die Biometrie-Klausel des EU AI Act den finalen Trilog?' })"
                  :disabled="loading || askBusy"
                  @keydown.enter.prevent="runAskMode"
                />
                <button class="ms-btn ms-btn-ghost" @click="runAskMode" :disabled="!askQuestion.trim() || loading || askBusy">
                  <span v-if="askBusy">…</span>
                  <span v-else>{{ $tr('Research →', '研究 →', { de: 'Recherche →', fr: 'Rechercher →' }) }}</span>
                </button>
              </div>
              <p v-if="askError" class="ms-error">{{ askError }}</p>
              <p v-if="askBusy" class="ms-hint">{{ $tr('Synthesizing briefing — Smart model, ~20–30s.', '正在合成简报 — Smart 模型,大约 20–30 秒。', { de: 'Briefing wird erstellt — Smart-Modell, ~20–30 Sek.', fr: 'Synthèse du brief — modèle Smart, ~20–30 s.' }) }}</p>

              <ul v-if="askDocs.length" class="ms-doc-list">
                <li
                  v-for="doc in askDocs"
                  :key="doc.url"
                  class="ms-doc"
                  role="button"
                  tabindex="0"
                  :title="$tr('Click to preview the generated briefing', '点击预览生成的简报', { de: 'Klicken zum Vorschau des generierten Briefings', fr: 'Cliquez pour prévisualiser le brief généré' })"
                  @click="previewDoc = doc"
                  @keydown.enter.prevent="previewDoc = doc"
                  @keydown.space.prevent="previewDoc = doc"
                >
                  <span class="ms-doc-icon" aria-hidden>◈</span>
                  <div class="ms-doc-info">
                    <div class="ms-doc-title">{{ truncate(doc.title, 70) }}</div>
                    <div class="ms-doc-meta">{{ doc.char_count.toLocaleString() }} {{ $tr('chars', '字符', { de: 'Zeichen', fr: 'caractères' }) }} · {{ truncate(doc.url, 72) }}</div>
                  </div>
                  <button @click.stop="removeUrlDocByRef(doc)" class="ms-x" aria-label="Remove">×</button>
                </li>
              </ul>
            </section>

            <!-- 01b — URL -->
            <section class="ms-block">
              <header class="ms-block-head">
                <span class="ms-block-label">{{ $tr('01b · URL Import', '01b · 网址导入', { de: '01b · URL-Import' }) }}</span>
                <span class="ms-block-meta">{{ $tr('Paste article or report URL', '粘贴文章或报告网址', { de: 'Artikel- oder Berichts-URL einfügen', fr: `Collez l'URL d'un article ou d'un rapport` }) }}</span>
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
                  <span v-else>{{ $tr('Fetch →', '抓取 →', { de: 'Abrufen →', fr: 'Récupérer →' }) }}</span>
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
                  :title="$tr('Click to preview the extracted content', '点击预览提取的内容', { de: 'Klicken zum Vorschau des extrahierten Inhalts', fr: 'Cliquez pour prévisualiser le contenu extrait' })"
                  @click="previewDoc = doc"
                  @keydown.enter.prevent="previewDoc = doc"
                  @keydown.space.prevent="previewDoc = doc"
                >
                  <span class="ms-doc-icon" aria-hidden>◈</span>
                  <div class="ms-doc-info">
                    <div class="ms-doc-title">{{ truncate(doc.title, 70) }}</div>
                    <div class="ms-doc-meta">{{ doc.char_count.toLocaleString() }} {{ $tr('chars', '字符', { de: 'Zeichen', fr: 'caractères' }) }} · {{ truncate(doc.url, 72) }}</div>
                  </div>
                  <button @click.stop="removeUrlDocByRef(doc)" class="ms-x" aria-label="Remove">×</button>
                </li>
              </ul>

              <TrendingTopics :busy="urlFetching" @select="handleTrendingSelect" />
            </section>

            <div class="ms-divider"><span>{{ $tr('Input parameters', '输入参数', { de: 'Eingabeparameter', fr: `Paramètres d'entrée` }) }}</span></div>

            <!-- 02 — Prompt -->
            <section class="ms-block">
              <header class="ms-block-head">
                <span class="ms-block-label">{{ $tr('>_ 02 · Simulation Prompt', '>_ 02 · 模拟提示词', { de: '>_ 02 · Simulationsprompt' }) }}</span>
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
                  :placeholder="$tr('// Enter your simulation requirements in natural language (e.g., If a university announces the revocation of a disciplinary action against a student, what public opinion trends will emerge?)', '// 用自然语言描述你的模拟需求(例如:如果一所大学宣布撤销对一名学生的纪律处分,会出现哪些舆论走向?)', { de: '// Simulationsanforderungen in natürlicher Sprache eingeben (z. B. Wenn eine Universität die Rücknahme einer Disziplinarmaßnahme gegen einen Studenten ankündigt, welche öffentlichen Meinungstrends werden entstehen?)' })"
                  rows="6"
                  :disabled="loading"
                ></textarea>
                <div class="ms-engine-tag">{{ $tr('Engine: MiroShark-V1.0', '引擎:MiroShark-V1.0', { de: 'Engine: MiroShark-V1.0', fr: 'Moteur : MiroShark-V1.0' }) }}</div>
              </div>

              <div v-if="canShareScenarioLink" class="ms-share-row">
                <button
                  class="ms-share-btn"
                  :class="{ 'is-copied': shareLinkCopied }"
                  :title="$tr('Copy a URL that drops a reader into this pre-filled form', '复制可让读者直接进入此预填表单的链接', { de: 'URL kopieren, die einen Leser direkt in dieses vorausgefüllte Formular bringt', fr: 'Copiez une URL qui ouvre ce formulaire pré-rempli' })"
                  @click="copyScenarioShareLink"
                >
                  <svg viewBox="0 0 24 24" class="ms-share-svg" fill="currentColor" aria-hidden="true">
                    <path d="M3.9 12a3.1 3.1 0 0 1 3.1-3.1h4V7H7a5 5 0 0 0 0 10h4v-1.9H7A3.1 3.1 0 0 1 3.9 12Zm5.1 1h6v-2H9v2Zm8-6h-4v1.9h4a3.1 3.1 0 0 1 0 6.2h-4V17h4a5 5 0 0 0 0-10Z" />
                  </svg>
                  <span v-if="shareLinkCopied">{{ $tr('Link copied', '链接已复制', { de: 'Link kopiert', fr: 'Lien copié' }) }}</span>
                  <span v-else>{{ $tr('Share as link', '分享为链接', { de: 'Als Link teilen', fr: 'Partager le lien' }) }}</span>
                </button>
                <span class="ms-share-hint">
                  {{ $tr('Tweet this URL to invite anyone to run the same setup.', '发推此 URL,即可邀请他人运行相同设置。', { de: 'Diese URL tweeten, um andere einzuladen, das gleiche Setup auszuführen.', fr: 'Tweetez cette URL pour inviter qui vous voulez à lancer la même simulation.' }) }}
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
                <span v-if="!loading">{{ $tr('Launch Simulation', '启动模拟', { de: 'Simulation starten', fr: 'Lancer la simulation' }) }}</span>
                <span v-else>{{ $tr('Initializing…', '初始化中…', { de: 'Initialisierung…', fr: 'Initialisation…' }) }}</span>
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
  { num: '01', titleEn: 'You bring a scenario', titleZh: '你提供一个情景', titleDe: 'Sie bringen ein Szenario',
    descEn: 'MiroShark builds the world around it — extracts actors, stakes, and open questions from your input.',
    descZh: 'MiroShark 围绕它构建世界 — 从你的输入中提取角色、利害关系与待解问题。',
    descDe: 'MiroShark baut die Welt darum auf — extrahiert Akteure, Einsätze und offene Fragen aus Ihrer Eingabe.' },
  { num: '02', titleEn: 'Hundreds of grounded agents', titleZh: '数百个有据可依的智能体', titleDe: 'Hunderte fundierter Agenten',
    descEn: 'React on Twitter, Reddit, and a prediction market. Hour by hour, round after round.',
    descZh: '在 Twitter、Reddit 与预测市场上做出反应。每小时一轮,一轮接一轮。',
    descDe: 'Reagieren auf Twitter, Reddit und einem Vorhersagemarkt. Stunde für Stunde, Runde für Runde.' },
  { num: '03', titleEn: 'Steer the timeline', titleZh: '掌舵时间线', titleDe: 'Den Zeitverlauf steuern',
    descEn: 'Chat with any agent. Drop breaking news mid-run. Fork a counterfactual and watch it diverge.',
    descZh: '与任意智能体对话。在运行中投入突发新闻。派生一个反事实分支并观察其偏离。',
    descDe: 'Mit jedem Agenten chatten. Eilmeldungen während des Laufs einstreuen. Einen kontrafaktischen Zweig verzweigen und die Divergenz beobachten.' },
  { num: '04', titleEn: 'Get a report', titleZh: '生成报告', titleDe: 'Einen Bericht erhalten',
    descEn: 'A Substack-style write-up of what happened, citing actual posts and trades from the run.',
    descZh: 'Substack 风格的复盘文章,引用本次运行中的真实发帖与交易。',
    descDe: 'Eine Substack-artige Zusammenfassung des Geschehens, mit Zitaten aus echten Beiträgen und Trades des Laufs.' },
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
    urlError.value = tr('This URL has already been added.', '此网址已添加过。', { de: 'Diese URL wurde bereits hinzugefügt.', fr: 'Cette URL a déjà été ajoutée.' })
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
      urlError.value = res.error || tr('Failed to fetch URL.', '抓取网址失败。', { de: 'URL konnte nicht abgerufen werden.', fr: `Échec de la récupération de l'URL.` })
    }
  } catch (err) {
    urlError.value = err.message || tr('Failed to fetch URL.', '抓取网址失败。', { de: 'URL konnte nicht abgerufen werden.', fr: `Échec de la récupération de l'URL.` })
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
      askError.value = res.error || tr('Ask mode failed.', '提问模式失败。', { de: 'Fragemodus fehlgeschlagen.', fr: 'Le mode question a échoué.' })
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
    askError.value = err?.response?.data?.error || err?.message || tr('Ask mode failed.', '提问模式失败。', { de: 'Fragemodus fehlgeschlagen.', fr: 'Le mode question a échoué.' })
  } finally {
    askBusy.value = false
  }
}

const handleTrendingSelect = ({ url }) => {
  if (!url || urlFetching.value) return
  if (urlDocs.value.some(d => d.url === url)) {
    urlError.value = tr('This URL is already loaded.', '此网址已加载。', { de: 'Diese URL ist bereits geladen.', fr: 'Cette URL a déjà été chargée.' })
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
      return tr('Document pre-filled from a shared link — review the scenario below before launching.',
        '已通过分享链接预填文档 — 启动前请检查下方情景设置。',
        { de: 'Dokument aus geteiltem Link vorausgefüllt — Szenario unten vor dem Starten prüfen.' },
      )
    case 'ask':
      return tr('Question pre-filled from a shared link — click Research to synthesize the briefing, or edit the question first.',
        '已通过分享链接预填问题 — 点击「研究」合成简报,或先修改问题。',
        { de: 'Frage aus geteiltem Link vorausgefüllt — auf „Recherche" klicken, um das Briefing zu erstellen, oder die Frage zuerst bearbeiten.' },
      )
    case 'mixed':
      return tr('Scenario, document, and question pre-filled from a shared link — review the form below before launching.',
        '情景、文档与问题均已通过分享链接预填 — 启动前请检查下方表单。',
        { de: 'Szenario, Dokument und Frage aus geteiltem Link vorausgefüllt — Formular unten vor dem Starten prüfen.' },
      )
    default:
      return tr('Scenario pre-filled from a shared link — review the form below before launching.',
        '已通过分享链接预填情景 — 启动前请检查下方表单。',
        { de: 'Szenario aus geteiltem Link vorausgefüllt — Formular unten vor dem Starten prüfen.' },
      )
  }
})

const autoLaunchTemplate = async (slug) => {
  templateAutoLaunching.value = true
  templateAutoLaunchError.value = ''
  try {
    const res = await getTemplate(slug)
    if (!res?.success || !res.data) {
      templateAutoLaunchError.value = tr(`Couldn't load that template. The link may be stale.`,
        '无法加载该模板。链接可能已失效。',
        { de: 'Vorlage konnte nicht geladen werden. Der Link ist möglicherweise veraltet.' },
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
      tr(`Couldn't load that template. The link may be stale.`,
        '无法加载该模板。链接可能已失效。',
        { de: 'Vorlage konnte nicht geladen werden. Der Link ist möglicherweise veraltet.' },
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
      err?.message || tr('Copy failed — long-press the link to copy manually.', '复制失败 — 长按链接手动复制。', { de: 'Kopieren fehlgeschlagen — Link lang drücken, um manuell zu kopieren.' })
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
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
  overflow-x: clip;
  /* Background + star field are global now (App.vue .space-bg /
     .space-stars), so this container stays transparent and lets
     the shared deep-space layers show through. */
  background: transparent;
}

/* All page content sits above the global fixed bg/stars layers. */
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
.ms-nav-svg { width: 18px; height: 18px; display: block; }

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
.ms-prefill-icon { width: 16px; height: 16px; flex: none; color: #c4b5fd; }
.ms-file-icon { width: 18px; height: 18px; flex: none; color: #c4b5fd; }
.ms-share-svg { width: 15px; height: 15px; display: block; }
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

/* When a section's component renders nothing (e.g. HistoryDatabase with no
   local run history → only a v-if comment node remains), :empty matches —
   CSS ignores comment nodes — so the bordered wrapper collapses instead of
   showing an empty box. */
.ms-section:empty {
  display: none;
}

@media (max-width: 1023px) {
  .ms-side { order: 2; }
  .ms-console-wrap { order: 1; }
}
</style>
