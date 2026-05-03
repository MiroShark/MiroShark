<template>
  <div class="tree-layout">
    <DecisionTreeToolbar
      :tree="tree"
      :augmenting-big-picture="augmentingBigPicture"
      :augmenting-story-depth="augmentingStoryDepth"
      :researching-all="researchingAll"
      :synthesizing-all="synthesizingAll"
      :compiling-foresight="compilingForesight"
      :scoring-all="scoringAll"
      :auto-growing="autoGrowing"
      :foresight="foresight"
      :planning-infographics="planningInfographics"
      :infographic-plan="infographicPlan"
      :planning-education="planningEducation"
      :education-plan="educationPlan"
      @back="goBack"
      @map="goToMap"
      @augment-big-picture="augmentBigPicture"
      @augment-story-depth="augmentStoryDepth"
      @auto-grow="autoGrowAndAnalyse"
      @stop-auto-grow="stopAutoGrow"
      @research-all="researchAll"
      @stop-research="stopResearchAll"
      @synthesize-all="synthesizeAll"
      @stop-synthesize="stopSynthesizeAll"
      @score-all="scoreAll"
      @stop-score="stopScoreAll"
      @compile-foresight="compileForesight"
      @plan-infographics="planInfographics"
      @plan-education="planEducation"
    />

    <ProgressBanner v-if="researchingAll" label="Researching node" :progress="researchProgress" />
    <ProgressBanner v-if="synthesizingAll" label="Synthesizing node" :progress="synthProgress" />
    <ProgressBanner v-if="scoringAll" label="Scoring node" :progress="scoreProgress" />
    <ProgressBanner
      v-if="autoGrowing"
      :label="`Auto-grow [${autoGrowProgress.phase}]`"
      :progress="autoGrowProgress"
    />

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
import DecisionTreeToolbar from '../components/decision-tree/DecisionTreeToolbar.vue'
import ProgressBanner from '../components/decision-tree/ProgressBanner.vue'
import ForesightModal from '../components/ForesightModal.vue'
import EducationPlanModal from '../components/education/EducationPlanModal.vue'
import InfographicTimelineModal from '../components/infographics/InfographicTimelineModal.vue'
import TimelinePlayerModal from '../components/infographics/TimelinePlayerModal.vue'
import { getSession } from '../api/seedChat.js'
import { postTreeInit } from '../api/decisionTree.js'
import { useEducationPlan } from '../composables/useEducationPlan.js'
import { useForesightDocument } from '../composables/useForesightDocument.js'
import { useInfographicTimeline } from '../composables/useInfographicTimeline.js'
import { useDecisionTreeActions } from '../composables/useDecisionTreeActions.js'

const route = useRoute()
const router = useRouter()

const sessionId = route.params.sessionId
const tree = ref(null)
const loading = ref(true)
const error = ref('')
const statusMessage = ref('')

// Per-node loading flags: { [nodeId]: { expand?: bool, research?: bool } }
const busyMap = reactive({})

const {
  infographicPlan,
  infographicOpen,
  planningInfographics,
  selectedInfographicIndex,
  renderingInfographic,
  batchRenderingInfographics,
  batchRenderProgress,
  batchRenderError,
  infographicFormat,
  infographicAccounting,
  narrationScript,
  planningNarration,
  renderingNarration,
  timelinePlayerOpen,
  playerIndex,
  playerPlaying,
  playerAutoAdvance,
  timelinePlayerRef,
  generatingAllSlideClips,
  clipGenerationProgress,
  clipGenerationError,
  selectedInfographicSlide,
  currentInfographicRender,
  selectedNarrationBeat,
  currentSlideAudioRender,
  nextUnrenderedSlides,
  timelineRows,
  playerSlide,
  playerRender,
  playerAudio,
  playerBeat,
  loadInfographicState,
  clearInfographicArtifacts,
  hasInfographicRender,
  narrationBeatFor,
  planInfographics,
  regenerateInfographics,
  setInfographicFormat,
  renderSelectedInfographic,
  renderNextInfographics,
  openTimelinePlayer,
  closeTimelinePlayer,
  previousPlayerSlide,
  nextPlayerSlide,
  playCurrentSlide,
  onPlayerAudioEnded,
  planNarration,
  renderNarrationAudio,
  generateAllSlideClips,
  copyNarrationScript,
  copyInfographicPrompt,
  copyInfographicJson,
  downloadInfographicJson,
} = useInfographicTimeline({ sessionId, route, router, tree, error })

const {
  educationPlan,
  educationInfographicPlan,
  educationOpen,
  planningEducation,
  loadEducationState,
  planEducation,
  copyEducationJson,
  downloadEducationJson,
} = useEducationPlan({ sessionId, tree, infographicFormat, error })

const {
  foresight,
  foresightOpen,
  compilingForesight,
  renderedForesight,
  loadForesightState,
  compileForesight,
  regenerateForesight,
  copyForesight,
  downloadForesight,
} = useForesightDocument({ sessionId, tree, error })

const {
  researchingAll,
  researchProgress,
  synthesizingAll,
  synthProgress,
  scoringAll,
  scoreProgress,
  augmentingBigPicture,
  augmentingStoryDepth,
  autoGrowing,
  autoGrowProgress,
  onExpand,
  onResearch,
  researchAll,
  stopResearchAll,
  onSynthesize,
  synthesizeAll,
  stopSynthesizeAll,
  onScore,
  scoreAll,
  stopScoreAll,
  augmentStoryDepth,
  augmentBigPicture,
  autoGrowAndAnalyse,
  stopAutoGrow,
  onUpdateNode,
} = useDecisionTreeActions({ sessionId, tree, error, statusMessage, busyMap, clearInfographicArtifacts })



function goBack() {
  router.push({ name: 'SeedChat', query: { session: sessionId } })
}

function goToMap() {
  router.push({ name: 'DecisionTreeMap', params: { sessionId } })
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
    loadForesightState(session)
    loadEducationState(session)
    loadInfographicState(session)
  } catch (err) {
    error.value = err?.response?.data?.error || err.message
  } finally {
    loading.value = false
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

.tiny {
  padding: 0.3rem 0.55rem;
  font-size: 0.75rem;
}



@media (max-width: 900px) {
  .infographic-body { grid-template-columns: 1fr; }
  .slide-list { max-height: 220px; border-right: 0; border-bottom: 1px solid #1f2937; }
}
</style>
