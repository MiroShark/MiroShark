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
        type="button"
        class="story-btn"
        :disabled="!tree || augmentingBigPicture || augmentingStoryDepth || researchingAll || synthesizingAll || compilingForesight || scoringAll || autoGrowing"
        @click="augmentBigPicture"
      >{{ augmentingBigPicture ? 'Adding story…' : 'Add big-picture story 🌏' }}</button>
      <button
        type="button"
        class="depth-btn"
        :disabled="!tree || augmentingBigPicture || augmentingStoryDepth || researchingAll || synthesizingAll || compilingForesight || scoringAll || autoGrowing"
        @click="augmentStoryDepth"
      >{{ augmentingStoryDepth ? 'Adding depth…' : 'Add story depth 🔎' }}</button>
      <button
        v-if="!autoGrowing"
        type="button"
        class="auto-grow-btn"
        :disabled="!tree || researchingAll || synthesizingAll || scoringAll || compilingForesight"
        @click="autoGrowAndAnalyse"
      >Auto-grow & analyse 🌳</button>
      <button
        v-else
        type="button"
        class="stop-btn"
        @click="stopAutoGrow"
      >Stop auto-grow</button>
      <button
        v-if="!researchingAll"
        type="button"
        class="research-all-btn"
        :disabled="!tree || synthesizingAll || compilingForesight || scoringAll || autoGrowing"
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
        :disabled="!tree || researchingAll || compilingForesight || scoringAll || autoGrowing"
        @click="synthesizeAll"
      >Synthesize all ✨</button>
      <button
        v-else
        type="button"
        class="stop-btn"
        @click="stopSynthesizeAll"
      >Stop synth</button>
      <button
        v-if="!scoringAll"
        type="button"
        class="score-all-btn"
        :disabled="!tree || researchingAll || synthesizingAll || compilingForesight || autoGrowing"
        @click="scoreAll"
      >Score all 🏷️</button>
      <button
        v-else
        type="button"
        class="stop-btn"
        @click="stopScoreAll"
      >Stop scoring</button>
      <button
        type="button"
        class="foresight-btn"
        :disabled="!tree || researchingAll || synthesizingAll || compilingForesight || scoringAll || autoGrowing"
        @click="compileForesight"
      >{{ compilingForesight ? 'Compiling…' : (foresight ? 'View foresight 📄' : 'Compile foresight 📄') }}</button>
      <button
        type="button"
        class="infographic-btn"
        :disabled="!tree || researchingAll || synthesizingAll || compilingForesight || scoringAll || autoGrowing || planningInfographics"
        @click="planInfographics"
      >{{ planningInfographics ? 'Planning…' : (infographicPlan ? 'View infographics 🎨' : 'Create infographics 🎨') }}</button>
      <button
        type="button"
        class="education-btn"
        :disabled="!tree || planningEducation || researchingAll || synthesizingAll || compilingForesight || scoringAll || autoGrowing"
        @click="planEducation"
      >{{ planningEducation ? 'Planning education…' : (educationPlan ? 'View education plan 🧭' : 'Education plan 🧭') }}</button>
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

    <div v-if="scoringAll" class="research-progress-banner" role="status" aria-live="polite">
      <span class="spinner-dot"></span>
      <span class="spinner-dot"></span>
      <span class="spinner-dot"></span>
      <span class="progress-text">
        Scoring node {{ scoreProgress.current }} of {{ scoreProgress.total }}:
        <span class="progress-question">"{{ scoreProgress.label }}"</span>
      </span>
    </div>

    <div v-if="autoGrowing" class="research-progress-banner" role="status" aria-live="polite">
      <span class="spinner-dot"></span>
      <span class="spinner-dot"></span>
      <span class="spinner-dot"></span>
      <span class="progress-text">
        Auto-grow [{{ autoGrowProgress.phase }}] {{ autoGrowProgress.current }} of {{ autoGrowProgress.total }}:
        <span class="progress-question">"{{ autoGrowProgress.label }}"</span>
      </span>
    </div>

    <main class="tree-body">
      <div v-if="error" class="error">{{ error }}</div>
      <div v-if="statusMessage" class="status-message">{{ statusMessage }}</div>
      <div v-if="loading && !tree" class="loading">Loading tree…</div>

      <TreeNode
        v-if="tree"
        :node="tree"
        :busy-map="busyMap"
        @expand="onExpand"
        @research="onResearch"
        @update-node="onUpdateNode"
        @synthesize="onSynthesize"
        @score="onScore"
      />
    </main>

    <ForesightModal
      v-if="foresightOpen"
      :rendered-foresight="renderedForesight"
      :compiling="compilingForesight"
      @close="foresightOpen = false"
      @copy="copyForesight"
      @download="downloadForesight"
      @regenerate="regenerateForesight"
    />

    <EducationPlanModal
      v-if="educationOpen"
      :education-plan="educationPlan"
      :education-infographic-plan="educationInfographicPlan"
      :planning="planningEducation"
      @close="educationOpen = false"
      @copy-json="copyEducationJson"
      @download-json="downloadEducationJson"
      @regenerate="planEducation(true)"
    />

    <InfographicTimelineModal
      v-if="infographicOpen"
      :infographic-plan="infographicPlan"
      :infographic-accounting="infographicAccounting"
      :infographic-format="infographicFormat"
      :timeline-rows="timelineRows"
      :selected-index="selectedInfographicIndex"
      :selected-slide="selectedInfographicSlide"
      :planning-narration="planningNarration"
      :narration-script="narrationScript"
      :rendering-narration="renderingNarration"
      :generating-all-slide-clips="generatingAllSlideClips"
      :selected-narration-beat="selectedNarrationBeat"
      :current-slide-audio-render="currentSlideAudioRender"
      :clip-generation-progress="clipGenerationProgress"
      :clip-generation-error="clipGenerationError"
      :rendering-infographic="renderingInfographic"
      :batch-rendering-infographics="batchRenderingInfographics"
      :next-unrendered-slides="nextUnrenderedSlides"
      :batch-render-progress="batchRenderProgress"
      :batch-render-error="batchRenderError"
      :current-infographic-render="currentInfographicRender"
      :planning-infographics="planningInfographics"
      :has-infographic-render="hasInfographicRender"
      :narration-beat-for="narrationBeatFor"
      @close="infographicOpen = false"
      @set-format="setInfographicFormat"
      @select-slide="selectedInfographicIndex = $event"
      @plan-narration="planNarration"
      @render-narration-audio="renderNarrationAudio"
      @generate-all-slide-clips="generateAllSlideClips"
      @copy-narration-script="copyNarrationScript"
      @render-selected-infographic="renderSelectedInfographic"
      @render-next-infographics="renderNextInfographics"
      @copy-infographic-prompt="copyInfographicPrompt"
      @copy-infographic-json="copyInfographicJson"
      @download-infographic-json="downloadInfographicJson"
      @regenerate-infographics="regenerateInfographics"
      @open-timeline-player="openTimelinePlayer"
    />

    <TimelinePlayerModal
      v-if="timelinePlayerOpen"
      ref="timelinePlayerRef"
      :player-index="playerIndex"
      :slide-count="infographicPlan?.sequence?.length || 0"
      :aspect-ratio="infographicPlan?.aspect_ratio || '16:9'"
      :player-slide="playerSlide"
      :player-render="playerRender"
      :player-beat="playerBeat"
      :player-audio="playerAudio"
      :player-playing="playerPlaying"
      v-model:auto-advance="playerAutoAdvance"
      @close="closeTimelinePlayer"
      @previous="previousPlayerSlide"
      @next="nextPlayerSlide"
      @play="playCurrentSlide"
      @audio-ended="onPlayerAudioEnded"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TreeNode from '../components/TreeNode.vue'
import ForesightModal from '../components/ForesightModal.vue'
import EducationPlanModal from '../components/education/EducationPlanModal.vue'
import InfographicTimelineModal from '../components/infographics/InfographicTimelineModal.vue'
import TimelinePlayerModal from '../components/infographics/TimelinePlayerModal.vue'
import { getSession } from '../api/seedChat.js'
import {
  postTreeInit,
  postTreeExpand,
  postTreeResearch,
  postTreeUpdateNode,
  postTreeSynthesize,
  postCompileForesight,
  postTreeScore,
  postTreeAugmentBigPicture,
  postTreeAugmentStoryDepth,
} from '../api/decisionTree.js'
import {
  postInfographicPlan,
  postRenderInfographic,
  getInfographicAccounting,
} from '../api/infographics.js'
import {
  postInfographicNarrationPlan,
  postRenderInfographicAudio,
} from '../api/narration.js'
import { postEducationPlan } from '../api/education.js'
import { marked } from 'marked'

const route = useRoute()
const router = useRouter()

const sessionId = route.params.sessionId
const tree = ref(null)
const loading = ref(true)
const error = ref('')
const statusMessage = ref('')

// Per-node loading flags: { [nodeId]: { expand?: bool, research?: bool } }
const busyMap = reactive({})

const researchingAll = ref(false)
const stopRequested = ref(false)
const researchProgress = ref({ current: 0, total: 0, label: '' })

const synthesizingAll = ref(false)
const synthStopRequested = ref(false)
const synthProgress = ref({ current: 0, total: 0, label: '' })

const scoringAll = ref(false)
const scoreStopRequested = ref(false)
const scoreProgress = ref({ current: 0, total: 0, label: '' })

const augmentingBigPicture = ref(false)
const augmentingStoryDepth = ref(false)
const autoGrowing = ref(false)
const autoGrowStopRequested = ref(false)
const autoGrowProgress = ref({ phase: '', current: 0, total: 0, label: '' })

const foresight = ref('')
const foresightOpen = ref(false)
const compilingForesight = ref(false)
const educationPlan = ref(null)
const educationInfographicPlan = ref(null)
const educationOpen = ref(false)
const planningEducation = ref(false)
const infographicPlan = ref(null)
const infographicOpen = ref(false)
const planningInfographics = ref(false)
const selectedInfographicIndex = ref(0)
const infographicRenders = ref({})
const renderingInfographic = ref(false)
const batchRenderingInfographics = ref(false)
const batchRenderProgress = ref({ current: 0, total: 0, label: '' })
const batchRenderError = ref('')
const infographicFormat = ref('landscape')
const infographicAccounting = ref(null)
const narrationScript = ref(null)
const audioRender = ref(null)
const slideAudioRenders = ref({})
const planningNarration = ref(false)
const renderingNarration = ref(false)
const timelinePlayerOpen = ref(false)
const playerIndex = ref(0)
const playerPlaying = ref(false)
const playerAutoAdvance = ref(true)
const timelinePlayerRef = ref(null)
const generatingAllSlideClips = ref(false)
const clipGenerationProgress = ref({ current: 0, total: 0, label: '' })
const clipGenerationError = ref('')

const selectedInfographicSlide = computed(() =>
  infographicPlan.value?.sequence?.[selectedInfographicIndex.value] || null
)

function slideKeyForIndex(index) {
  const slide = infographicPlan.value?.sequence?.[index]
  return slide?.slide_id || String(index)
}

function renderForIndex(index) {
  const key = slideKeyForIndex(index)
  const stable = infographicRenders.value?.[key]
  if (stable) return stable
  const legacy = infographicRenders.value?.[String(index)]
  if (!legacy) return null
  if (legacy.slide_id && legacy.slide_id !== key) return null
  return legacy
}

function audioForIndex(index) {
  const key = slideKeyForIndex(index)
  const stable = slideAudioRenders.value?.[key]
  if (stable) return stable
  const legacy = slideAudioRenders.value?.[String(index)]
  if (!legacy) return null
  if (legacy.slide_id && legacy.slide_id !== key) return null
  return legacy
}

function hasInfographicRender(index) {
  return !!renderForIndex(index)
}

const currentInfographicRender = computed(() =>
  renderForIndex(selectedInfographicIndex.value)
)

const selectedNarrationBeat = computed(() => narrationBeatFor(selectedInfographicIndex.value))
const currentSlideAudioRender = computed(() => audioForIndex(selectedInfographicIndex.value))
const nextUnrenderedSlides = computed(() => {
  const sequence = infographicPlan.value?.sequence || []
  return sequence
    .map((slide, index) => ({ slide, index, key: slide.slide_id || String(index) }))
    .filter(row => !renderForIndex(row.index))
    .slice(0, Math.max(0, Math.min(5, infographicAccounting.value?.openai_remaining_today ?? 5)))
})

function narrationBeatFor(index) {
  const key = slideKeyForIndex(index)
  return narrationScript.value?.slides?.find((beat) => beat.slide_id === key || beat.slide_index === index) || null
}

const timelineRows = computed(() =>
  (infographicPlan.value?.sequence || []).map((slide, index) => ({
    slide,
    index,
    slideKey: slide.slide_id || String(index),
    ...timelineDepthFor(slide),
  }))
)

function timelineDepthFor(slide) {
  return {
    depth: Number.isInteger(slide?.depth) ? slide.depth : 0,
    chapter: slide?.chapter || 'Story beat',
    parent: slide?.parent || '',
    parentSlideIndex: Number.isInteger(slide?.parent_slide_index) ? slide.parent_slide_index : null,
  }
}

const playerSlide = computed(() => infographicPlan.value?.sequence?.[playerIndex.value] || null)
const playerRender = computed(() => renderForIndex(playerIndex.value))
const playerAudio = computed(() => audioForIndex(playerIndex.value))
const playerBeat = computed(() => narrationBeatFor(playerIndex.value))

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

function shouldOpenInfographicsOnLoad() {
  return route.query.infographics !== '0'
}

async function loadTree() {
  loading.value = true
  error.value = ''
  statusMessage.value = ''
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
    if (session?.education_plan) educationPlan.value = session.education_plan
    if (session?.education_infographic_plan) educationInfographicPlan.value = session.education_infographic_plan
    if (session?.infographic_plan) {
      infographicPlan.value = session.infographic_plan
      infographicOpen.value = shouldOpenInfographicsOnLoad()
    }
    if (session?.infographic_renders) {
      infographicRenders.value = session.infographic_renders
    }
    if (session?.narration_script) {
      narrationScript.value = session.narration_script
    }
    if (session?.audio_renders?.narration) {
      audioRender.value = session.audio_renders.narration
    }
    if (session?.audio_renders?.slides) {
      slideAudioRenders.value = session.audio_renders.slides
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

async function onScore(nodeId) {
  setBusy(nodeId, 'score', true)
  error.value = ''
  try {
    await postTreeScore({ session_id: sessionId, node_id: nodeId })
    const session = await getSession(sessionId)
    if (session?.tree) tree.value = session.tree
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    setBusy(nodeId, 'score', false)
  }
}

async function scoreAll() {
  if (!tree.value || scoringAll.value) return
  const nodes = flattenBfs(tree.value).filter(
    n => (n.evidence?.length > 0 || (n.summary && n.summary.trim()))
  )
  if (nodes.length === 0) {
    error.value = 'Nothing to score yet — run Research and Synthesize first.'
    return
  }
  scoringAll.value = true
  scoreStopRequested.value = false
  error.value = ''
  scoreProgress.value = { current: 0, total: nodes.length, label: '' }
  for (let i = 0; i < nodes.length; i++) {
    if (scoreStopRequested.value) break
    const node = nodes[i]
    scoreProgress.value = {
      current: i + 1,
      total: nodes.length,
      label: node.question,
    }
    setBusy(node.id, 'score', true)
    try {
      await postTreeScore({ session_id: sessionId, node_id: node.id })
      const session = await getSession(sessionId)
      if (session?.tree) tree.value = session.tree
    } catch (err) {
      const msg = err?.response?.data?.error || err.message
      error.value = `Node ${i + 1} failed: ${msg}. Continuing.`
    } finally {
      setBusy(node.id, 'score', false)
    }
  }
  scoringAll.value = false
  scoreProgress.value = { current: 0, total: 0, label: '' }
}

async function augmentStoryDepth() {
  if (!tree.value || augmentingStoryDepth.value) return
  augmentingStoryDepth.value = true
  error.value = ''
  try {
    const data = await postTreeAugmentStoryDepth({ session_id: sessionId })
    if (data?.tree) tree.value = data.tree
    infographicPlan.value = null
    infographicRenders.value = {}
    narrationScript.value = null
    audioRender.value = null
    slideAudioRenders.value = {}
    if (data?.added === 0) {
      statusMessage.value = 'Story-depth nodes are already present. Next step: research/synthesize those nodes, then regenerate the infographic timeline.'
    } else {
      statusMessage.value = `Added ${data.added} story-depth nodes. Regenerate the infographic timeline after research/synthesis.`
    }
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    augmentingStoryDepth.value = false
  }
}

function stopScoreAll() {
  scoreStopRequested.value = true
}

async function augmentBigPicture() {
  if (!tree.value || augmentingBigPicture.value) return
  augmentingBigPicture.value = true
  error.value = ''
  try {
    const data = await postTreeAugmentBigPicture({ session_id: sessionId })
    if (data?.tree) tree.value = data.tree
    infographicPlan.value = null
    infographicRenders.value = {}
    narrationScript.value = null
    audioRender.value = null
    if (data?.added === 0) {
      error.value = 'Big-picture story nodes are already present.'
    }
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    augmentingBigPicture.value = false
  }
}

async function autoGrowAndAnalyse() {
  if (!tree.value || autoGrowing.value) return
  autoGrowing.value = true
  autoGrowStopRequested.value = false
  error.value = ''

  try {
    // Phase 1: Expand each direct child of the root that has no children yet
    const roots = (tree.value.children || []).filter(n => !(n.children?.length > 0))
    autoGrowProgress.value = { phase: 'expanding', current: 0, total: roots.length, label: '' }
    for (let i = 0; i < roots.length; i++) {
      if (autoGrowStopRequested.value) break
      const node = roots[i]
      autoGrowProgress.value = { phase: 'expanding', current: i + 1, total: roots.length, label: node.question }
      setBusy(node.id, 'expand', true)
      try {
        await postTreeExpand({ session_id: sessionId, node_id: node.id })
        const session = await getSession(sessionId)
        if (session?.tree) tree.value = session.tree
      } catch (err) {
        const msg = err?.response?.data?.error || err.message
        error.value = `Expand ${i + 1} failed: ${msg}. Continuing.`
      } finally {
        setBusy(node.id, 'expand', false)
      }
    }

    if (autoGrowStopRequested.value) return

    // Phase 2: Research every node without evidence
    const researchTargets = flattenBfs(tree.value).filter(n => !(n.evidence?.length > 0))
    autoGrowProgress.value = { phase: 'researching', current: 0, total: researchTargets.length, label: '' }
    for (let i = 0; i < researchTargets.length; i++) {
      if (autoGrowStopRequested.value) break
      const node = researchTargets[i]
      autoGrowProgress.value = { phase: 'researching', current: i + 1, total: researchTargets.length, label: node.question }
      setBusy(node.id, 'research', true)
      try {
        await postTreeResearch({ session_id: sessionId, node_id: node.id })
        const session = await getSession(sessionId)
        if (session?.tree) tree.value = session.tree
      } catch (err) {
        const msg = err?.response?.data?.error || err.message
        error.value = `Research ${i + 1} failed: ${msg}. Continuing.`
      } finally {
        setBusy(node.id, 'research', false)
      }
    }

    if (autoGrowStopRequested.value) return

    // Phase 3: Synthesize every node with evidence but no summary
    const synthTargets = flattenBfs(tree.value).filter(
      n => (n.evidence?.length > 0) && !n.summary
    )
    autoGrowProgress.value = { phase: 'synthesising', current: 0, total: synthTargets.length, label: '' }
    for (let i = 0; i < synthTargets.length; i++) {
      if (autoGrowStopRequested.value) break
      const node = synthTargets[i]
      autoGrowProgress.value = { phase: 'synthesising', current: i + 1, total: synthTargets.length, label: node.question }
      setBusy(node.id, 'synthesize', true)
      try {
        await postTreeSynthesize({ session_id: sessionId, node_id: node.id })
        const session = await getSession(sessionId)
        if (session?.tree) tree.value = session.tree
      } catch (err) {
        const msg = err?.response?.data?.error || err.message
        error.value = `Synthesise ${i + 1} failed: ${msg}. Continuing.`
      } finally {
        setBusy(node.id, 'synthesize', false)
      }
    }

    if (autoGrowStopRequested.value) return

    // Phase 4: Score every node that has evidence or summary
    const scoreTargets = flattenBfs(tree.value).filter(
      n => (n.evidence?.length > 0 || (n.summary && n.summary.trim()))
    )
    autoGrowProgress.value = { phase: 'scoring', current: 0, total: scoreTargets.length, label: '' }
    for (let i = 0; i < scoreTargets.length; i++) {
      if (autoGrowStopRequested.value) break
      const node = scoreTargets[i]
      autoGrowProgress.value = { phase: 'scoring', current: i + 1, total: scoreTargets.length, label: node.question }
      setBusy(node.id, 'score', true)
      try {
        await postTreeScore({ session_id: sessionId, node_id: node.id })
        const session = await getSession(sessionId)
        if (session?.tree) tree.value = session.tree
      } catch (err) {
        const msg = err?.response?.data?.error || err.message
        error.value = `Score ${i + 1} failed: ${msg}. Continuing.`
      } finally {
        setBusy(node.id, 'score', false)
      }
    }
  } finally {
    autoGrowing.value = false
    autoGrowProgress.value = { phase: '', current: 0, total: 0, label: '' }
  }
}

function stopAutoGrow() {
  autoGrowStopRequested.value = true
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


async function planEducation(force = false) {
  if (planningEducation.value) return
  if (educationPlan.value && !force) {
    educationOpen.value = true
    return
  }
  planningEducation.value = true
  error.value = ''
  try {
    const data = await postEducationPlan({
      session_id: sessionId,
      format: infographicFormat.value || 'tiktok',
    })
    if (data?.education_plan) educationPlan.value = data.education_plan
    if (data?.infographic_plan) educationInfographicPlan.value = data.infographic_plan
    educationOpen.value = true
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    planningEducation.value = false
  }
}


async function planInfographics() {
  if (!tree.value || planningInfographics.value) return
  if (infographicPlan.value && !infographicOpen.value) {
    infographicOpen.value = true
    router.replace({ name: 'DecisionTree', params: { sessionId }, query: { ...route.query, infographics: '1' } })
    return
  }
  await regenerateInfographics()
}

async function regenerateInfographics() {
  if (!tree.value || planningInfographics.value) return
  planningInfographics.value = true
  error.value = ''
  statusMessage.value = ''
  try {
    const data = await postInfographicPlan({ session_id: sessionId })
    if (data?.infographic_plan) {
      infographicPlan.value = data.infographic_plan
      infographicRenders.value = {}
      narrationScript.value = null
      audioRender.value = null
      slideAudioRenders.value = {}
      await refreshInfographicAccounting()
      selectedInfographicIndex.value = 0
      infographicOpen.value = true
      router.replace({ name: 'DecisionTree', params: { sessionId }, query: { ...route.query, infographics: '1' } })
    }
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    planningInfographics.value = false
  }
}

async function refreshInfographicAccounting() {
  try {
    const data = await getInfographicAccounting(sessionId)
    if (data?.render_accounting) infographicAccounting.value = data.render_accounting
  } catch {
    // Non-critical; rendering endpoint still enforces limits server-side.
  }
}

function setInfographicFormat(format) {
  if (infographicFormat.value === format) return
  infographicFormat.value = format
  infographicPlan.value = null
  infographicRenders.value = {}
  narrationScript.value = null
  audioRender.value = null
  slideAudioRenders.value = {}
  regenerateInfographics()
}

async function renderSelectedInfographic() {
  if (!infographicPlan.value || renderingInfographic.value || batchRenderingInfographics.value) return
  renderingInfographic.value = true
  error.value = ''
  batchRenderError.value = ''
  try {
    const data = await renderInfographicAtIndex(selectedInfographicIndex.value)
    if (data?.render) {
      storeInfographicRender(selectedInfographicIndex.value, data)
      if (data.render_accounting) infographicAccounting.value = data.render_accounting
    }
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    renderingInfographic.value = false
  }
}

async function renderInfographicAtIndex(index) {
  return postRenderInfographic({
    session_id: sessionId,
    slide_index: index,
    slide_id: slideKeyForIndex(index),
    provider: 'openai',
    render_mode: 'strict',
    model: 'gpt-image-2',
    aspect_ratio: infographicPlan.value?.aspect_ratio || (infographicFormat.value === 'tiktok' ? '9:16' : '16:9'),
    image_size: '1K',
  })
}

function storeInfographicRender(index, data) {
  if (!data?.render) return
  infographicRenders.value = {
    ...infographicRenders.value,
    [data.slide_id || data.render.slide_id || slideKeyForIndex(index)]: data.render,
  }
}

async function renderNextInfographics() {
  if (!infographicPlan.value || batchRenderingInfographics.value || renderingInfographic.value) return
  const targets = nextUnrenderedSlides.value
  if (!targets.length) return
  batchRenderingInfographics.value = true
  batchRenderError.value = ''
  error.value = ''
  batchRenderProgress.value = { current: 0, total: targets.length, label: 'Starting…' }
  try {
    for (let i = 0; i < targets.length; i += 1) {
      const target = targets[i]
      batchRenderProgress.value = { current: i + 1, total: targets.length, label: `Rendering slide ${target.index + 1}: ${target.slide.title}` }
      try {
        const data = await renderInfographicAtIndex(target.index)
        storeInfographicRender(target.index, data)
        if (data?.render_accounting) infographicAccounting.value = data.render_accounting
      } catch (err) {
        const msg = _clipErrorMessage(err)
        batchRenderError.value = `Stopped at slide ${target.index + 1}: ${msg}`
        break
      }
    }
  } finally {
    batchRenderingInfographics.value = false
  }
}


function openTimelinePlayer() {
  if (!infographicPlan.value?.sequence?.length) return
  playerIndex.value = selectedInfographicIndex.value || 0
  playerPlaying.value = false
  timelinePlayerOpen.value = true
}

function closeTimelinePlayer() {
  if (timelinePlayerRef.value?.audioRef) timelinePlayerRef.value.audioRef.pause()
  playerPlaying.value = false
  timelinePlayerOpen.value = false
}

function previousPlayerSlide() {
  if (playerIndex.value <= 0) return
  playerIndex.value -= 1
  playerPlaying.value = false
}

function nextPlayerSlide() {
  const total = infographicPlan.value?.sequence?.length || 0
  if (playerIndex.value >= total - 1) return
  playerIndex.value += 1
  playerPlaying.value = false
}

async function playCurrentSlide() {
  const audio = timelinePlayerRef.value?.audioRef
  if (!audio || !playerAudio.value) return
  try {
    audio.currentTime = 0
    await audio.play()
    playerPlaying.value = true
  } catch {
    error.value = 'Audio playback was blocked by the browser. Press play on the audio control.'
  }
}

function onPlayerAudioEnded() {
  playerPlaying.value = false
  if (playerAutoAdvance.value) {
    const total = infographicPlan.value?.sequence?.length || 0
    if (playerIndex.value < total - 1) {
      playerIndex.value += 1
      setTimeout(() => playCurrentSlide(), 150)
    }
  }
}

async function planNarration() {
  if (!infographicPlan.value || planningNarration.value) return
  planningNarration.value = true
  error.value = ''
  clipGenerationError.value = ''
  try {
    const data = await postInfographicNarrationPlan({
      session_id: sessionId,
      format: infographicFormat.value,
      target_seconds: infographicFormat.value === 'tiktok' ? 75 : 90,
    })
    if (data?.narration_script) {
      narrationScript.value = data.narration_script
      audioRender.value = null
    }
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    planningNarration.value = false
  }
}

async function renderNarrationAudio() {
  if (!infographicPlan.value || !narrationScript.value || renderingNarration.value) return
  renderingNarration.value = true
  error.value = ''
  clipGenerationError.value = ''
  try {
    const data = await postRenderInfographicAudio({
      session_id: sessionId,
      format: infographicFormat.value,
      slide_index: selectedInfographicIndex.value,
      slide_id: slideKeyForIndex(selectedInfographicIndex.value),
    })
    if (data?.narration_script) narrationScript.value = data.narration_script
    if (data?.audio_render) {
      slideAudioRenders.value = {
        ...slideAudioRenders.value,
        [data.audio_render.slide_id || slideKeyForIndex(selectedInfographicIndex.value)]: data.audio_render,
      }
    }
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    renderingNarration.value = false
  }
}

function _clipErrorMessage(err) {
  return err?.response?.data?.error || err.message || String(err)
}

async function generateAllSlideClips() {
  if (!narrationScript.value?.slides?.length || generatingAllSlideClips.value) return
  generatingAllSlideClips.value = true
  clipGenerationError.value = ''
  error.value = ''
  const beats = narrationScript.value.slides
  clipGenerationProgress.value = { current: 0, total: beats.length, label: 'Starting…' }
  try {
    for (let i = 0; i < beats.length; i += 1) {
      const beat = beats[i]
      const key = beat.slide_id || String(beat.slide_index)
      if (slideAudioRenders.value?.[key]) {
        clipGenerationProgress.value = { current: i + 1, total: beats.length, label: `Slide ${beat.slide_index + 1} already exists` }
        continue
      }
      clipGenerationProgress.value = { current: i + 1, total: beats.length, label: `Generating slide ${beat.slide_index + 1}…` }
      try {
        const data = await postRenderInfographicAudio({
          session_id: sessionId,
          format: infographicFormat.value,
          slide_index: beat.slide_index,
          slide_id: beat.slide_id,
          provider: 'local_piper',
        })
        if (data?.narration_script) narrationScript.value = data.narration_script
        if (data?.audio_render) {
          slideAudioRenders.value = {
            ...slideAudioRenders.value,
            [key]: data.audio_render,
          }
        }
      } catch (err) {
        const msg = _clipErrorMessage(err)
        clipGenerationError.value = `Stopped at slide ${beat.slide_index + 1}: ${msg}`
        break
      }
    }
  } finally {
    generatingAllSlideClips.value = false
    const done = Object.keys(slideAudioRenders.value || {}).length
    clipGenerationProgress.value = {
      current: Math.min(done, beats.length),
      total: beats.length,
      label: clipGenerationError.value ? 'Paused — retry later' : 'Complete',
    }
  }
}

async function copyNarrationScript() {
  if (!narrationScript.value?.full_voiceover) return
  try {
    await navigator.clipboard.writeText(narrationScript.value.full_voiceover)
  } catch {
    error.value = 'Copy failed — your browser blocked clipboard access.'
  }
}

async function copyEducationJson() {
  if (!educationPlan.value) return
  try {
    await navigator.clipboard.writeText(JSON.stringify({ education_plan: educationPlan.value, infographic_plan: educationInfographicPlan.value }, null, 2))
  } catch {
    error.value = 'Copy failed — your browser blocked clipboard access.'
  }
}

function downloadEducationJson() {
  if (!educationPlan.value) return
  const date = new Date().toISOString().slice(0, 10)
  const slug = (tree.value?.question || 'education-plan')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60) || 'education-plan'
  const blob = new Blob([JSON.stringify({ education_plan: educationPlan.value, infographic_plan: educationInfographicPlan.value }, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `education-plan-${slug}-${date}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}


async function copyInfographicPrompt() {
  if (!selectedInfographicSlide.value?.image_prompt) return
  try {
    await navigator.clipboard.writeText(selectedInfographicSlide.value.image_prompt)
  } catch {
    error.value = 'Copy failed — your browser blocked clipboard access.'
  }
}

async function copyInfographicJson() {
  if (!infographicPlan.value) return
  try {
    await navigator.clipboard.writeText(JSON.stringify(infographicPlan.value, null, 2))
  } catch {
    error.value = 'Copy failed — your browser blocked clipboard access.'
  }
}

function downloadInfographicJson() {
  if (!infographicPlan.value) return
  const date = new Date().toISOString().slice(0, 10)
  const slug = (tree.value?.question || 'infographics')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60) || 'infographics'
  const blob = new Blob([JSON.stringify(infographicPlan.value, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `infographic-plan-${slug}-${date}.json`
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
.status-message {
  margin: 0 0 1rem;
  padding: 0.75rem 1rem;
  border: 1px solid #315a72;
  border-radius: 8px;
  background: #0f2635;
  color: #d7efff;
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

.score-all-btn {
  background: #4a3a4a;
  color: #f5d6f5;
  border: 1px solid #6a5a6a;
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 500;
  margin-left: 0.5rem;
}
.score-all-btn:hover { background: #5a4655; }
.score-all-btn:disabled { opacity: 0.4; cursor: not-allowed; }

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

.depth-btn,
.story-btn {
  background: #1f3a4a;
  color: #d7efff;
  border: 1px solid #315a72;
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 500;
  margin-left: 0.5rem;
}
.depth-btn:hover,
.story-btn:hover { background: #29495d; }
.depth-btn:disabled,
.story-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.auto-grow-btn {
  background: #2a4a3a;
  color: #d6f5e0;
  border: 1px solid #3a6a4a;
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 500;
  margin-left: 0.5rem;
}
.auto-grow-btn:hover { background: #355945; }
.auto-grow-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.infographic-btn {
  background: #2d3f55;
  color: #dbeafe;
  border: 1px solid #426084;
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 500;
  margin-left: 0.5rem;
}
.infographic-btn:hover { background: #36506d; }
.infographic-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.foresight-footer .tiny,
.tiny {
  padding: 0.3rem 0.55rem;
  font-size: 0.75rem;
}



@media (max-width: 900px) {
  .topbar { flex-wrap: wrap; }
  .topic { flex-basis: 100%; }
  .infographic-body { grid-template-columns: 1fr; }
  .slide-list { max-height: 220px; border-right: 0; border-bottom: 1px solid #1f2937; }
}


.education-btn {
  padding: 0.55rem 0.9rem;
  border: 1px solid #315c7d;
  border-radius: 999px;
  background: #102a3d;
  color: #d7efff;
  cursor: pointer;
}
.education-btn:hover { background: #173a53; }
.education-btn:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
