<template>
  <header class="decision-tree-toolbar">
    <div class="toolbar-title-row">
      <button class="back-btn" type="button" @click="$emit('back')">← Back to chat</button>
      <div class="brand">DECISION TREE</div>
      <div class="topic" :title="tree?.question || 'Loading…'">{{ tree?.question || 'Loading…' }}</div>
    </div>

    <div class="toolbar-actions" aria-label="Decision tree actions">
      <button type="button" class="map-view-btn" :disabled="!tree" @click="$emit('map')">Map view 🗺️</button>
      <button type="button" class="story-btn" :disabled="busyDisabled" @click="$emit('augment-big-picture')">{{ augmentingBigPicture ? 'Adding story…' : 'Add big-picture story 🌏' }}</button>
      <button type="button" class="depth-btn" :disabled="busyDisabled" @click="$emit('augment-story-depth')">{{ augmentingStoryDepth ? 'Adding depth…' : 'Add story depth 🔎' }}</button>
      <button v-if="!autoGrowing" type="button" class="auto-grow-btn" :disabled="!tree || researchingAll || synthesizingAll || scoringAll || compilingForesight" @click="$emit('auto-grow')">Auto-grow & analyse 🌳</button>
      <button v-else type="button" class="stop-btn" @click="$emit('stop-auto-grow')">Stop auto-grow</button>
      <button v-if="!researchingAll" type="button" class="research-all-btn" :disabled="!tree || synthesizingAll || compilingForesight || scoringAll || autoGrowing" @click="$emit('research-all')">Research all 🔁</button>
      <button v-else type="button" class="stop-btn" @click="$emit('stop-research')">Stop research</button>
      <button v-if="!synthesizingAll" type="button" class="synthesize-all-btn" :disabled="!tree || researchingAll || compilingForesight || scoringAll || autoGrowing" @click="$emit('synthesize-all')">Synthesize all ✨</button>
      <button v-else type="button" class="stop-btn" @click="$emit('stop-synthesize')">Stop synth</button>
      <button v-if="!scoringAll" type="button" class="score-all-btn" :disabled="!tree || researchingAll || synthesizingAll || compilingForesight || autoGrowing" @click="$emit('score-all')">Score all 🏷️</button>
      <button v-else type="button" class="stop-btn" @click="$emit('stop-score')">Stop scoring</button>
      <button type="button" class="foresight-btn" :disabled="!tree || researchingAll || synthesizingAll || compilingForesight || scoringAll || autoGrowing" @click="$emit('compile-foresight')">{{ compilingForesight ? 'Compiling…' : (foresight ? 'View foresight 📄' : 'Compile foresight 📄') }}</button>
      <button type="button" class="infographic-btn" :disabled="!tree || researchingAll || synthesizingAll || compilingForesight || scoringAll || autoGrowing || planningInfographics" @click="$emit('plan-infographics')">{{ planningInfographics ? 'Planning…' : (infographicPlan ? 'View infographics 🎨' : 'Create infographics 🎨') }}</button>
      <button type="button" class="education-btn" :disabled="!tree || planningEducation || researchingAll || synthesizingAll || compilingForesight || scoringAll || autoGrowing" @click="$emit('plan-education')">{{ planningEducation ? 'Planning education…' : (educationPlan ? 'View education plan 🧭' : 'Education plan 🧭') }}</button>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  tree: { type: Object, default: null },
  augmentingBigPicture: { type: Boolean, default: false },
  augmentingStoryDepth: { type: Boolean, default: false },
  researchingAll: { type: Boolean, default: false },
  synthesizingAll: { type: Boolean, default: false },
  compilingForesight: { type: Boolean, default: false },
  scoringAll: { type: Boolean, default: false },
  autoGrowing: { type: Boolean, default: false },
  foresight: { type: String, default: '' },
  planningInfographics: { type: Boolean, default: false },
  infographicPlan: { type: Object, default: null },
  planningEducation: { type: Boolean, default: false },
  educationPlan: { type: Object, default: null },
})

defineEmits([
  'back', 'map', 'augment-big-picture', 'augment-story-depth', 'auto-grow', 'stop-auto-grow',
  'research-all', 'stop-research', 'synthesize-all', 'stop-synthesize', 'score-all', 'stop-score',
  'compile-foresight', 'plan-infographics', 'plan-education',
])

const busyDisabled = computed(() => !props.tree || props.augmentingBigPicture || props.augmentingStoryDepth || props.researchingAll || props.synthesizingAll || props.compilingForesight || props.scoringAll || props.autoGrowing)
</script>

<style scoped>
.decision-tree-toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(0, 3fr);
  align-items: center;
  gap: 0.75rem 1rem;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid #222;
  background: #080808;
}
.toolbar-title-row {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr);
  align-items: center;
  gap: 1rem;
  min-width: 0;
}
.toolbar-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 0.5rem;
  min-width: 0;
}
.toolbar-actions button { flex: 0 0 auto; }
.back-btn { background: transparent; border: 1px solid #333; color: #ddd; padding: 0.35rem 0.7rem; border-radius: 4px; cursor: pointer; font-family: inherit; font-size: 0.85rem; }
.back-btn:hover { background: #1a1a1a; }
.brand { font-weight: bold; letter-spacing: 0.15em; white-space: nowrap; }
.topic { color: #aaa; font-size: 0.9rem; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.research-all-btn, .stop-btn { background: #2a4a2a; color: #d6f5d6; border: 1px solid #3a6a3a; padding: 0.4rem 0.8rem; border-radius: 4px; cursor: pointer; font-family: inherit; font-size: 0.85rem; font-weight: 500; }
.research-all-btn:hover { background: #335933; }
.research-all-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.stop-btn { background: #4a2a2a; color: #f5d6d6; border-color: #6a3a3a; }
.stop-btn:hover { background: #593333; }
.synthesize-all-btn, .score-all-btn, .foresight-btn, .map-view-btn, .depth-btn, .story-btn, .auto-grow-btn, .infographic-btn { padding: 0.4rem 0.8rem; border-radius: 4px; cursor: pointer; font-family: inherit; font-size: 0.85rem; font-weight: 500; }
.synthesize-all-btn { background: #2a2a4a; color: #d6d6f5; border: 1px solid #3a3a6a; }
.synthesize-all-btn:hover { background: #353559; }
.score-all-btn { background: #4a3a4a; color: #f5d6f5; border: 1px solid #6a5a6a; }
.score-all-btn:hover { background: #5a4655; }
.foresight-btn, .map-view-btn { background: #4a3a2a; color: #f5e8d6; border: 1px solid #6a5a3a; }
.foresight-btn:hover, .map-view-btn:hover { background: #5a4a35; }
.depth-btn, .story-btn { background: #1f3a4a; color: #d7efff; border: 1px solid #315a72; }
.depth-btn:hover, .story-btn:hover { background: #29495d; }
.auto-grow-btn { background: #2a4a3a; color: #d6f5e0; border: 1px solid #3a6a4a; }
.auto-grow-btn:hover { background: #355945; }
.infographic-btn { background: #2d3f55; color: #dbeafe; border: 1px solid #426084; }
.infographic-btn:hover { background: #36506d; }
.education-btn { padding: 0.55rem 0.9rem; border: 1px solid #315c7d; border-radius: 999px; background: #102a3d; color: #d7efff; cursor: pointer; }
.education-btn:hover { background: #173a53; }
.synthesize-all-btn:disabled, .score-all-btn:disabled, .foresight-btn:disabled, .map-view-btn:disabled, .depth-btn:disabled, .story-btn:disabled, .auto-grow-btn:disabled, .infographic-btn:disabled, .education-btn:disabled { opacity: 0.4; cursor: not-allowed; }
@media (max-width: 1400px) {
  .decision-tree-toolbar { grid-template-columns: 1fr; }
  .toolbar-actions { justify-content: flex-start; }
}
@media (max-width: 700px) {
  .toolbar-title-row { grid-template-columns: auto 1fr; }
  .topic { grid-column: 1 / -1; }
}
</style>
