<template>
  <div class="foresight-overlay" @click.self="$emit('close')">
    <div class="timeline-player-modal">
      <header class="foresight-header">
        <div>
          <h2>Slide timeline player</h2>
          <p class="modal-subtitle">Slide {{ playerIndex + 1 }} of {{ slideCount }} · image + matching audio clip</p>
        </div>
        <button type="button" class="close" @click="$emit('close')">×</button>
      </header>

      <div v-if="playerSlide" class="timeline-player-body">
        <div class="player-stage" :class="{ vertical: aspectRatio === '9:16' }">
          <img v-if="playerRender" :src="playerRender.url" :alt="playerSlide.title" />
          <div v-else class="player-placeholder">
            <strong>{{ playerSlide.title }}</strong>
            <span>No rendered image for this slide yet.</span>
          </div>
        </div>
        <aside class="player-side">
          <div class="slide-type">{{ playerSlide.slide_type }}</div>
          <h3>{{ playerSlide.title }}</h3>
          <p>{{ playerSlide.message }}</p>
          <div v-if="playerBeat" class="slide-narration-beat">
            <strong>Audio beat · {{ playerBeat.duration_seconds }}s</strong>
            <span>{{ playerBeat.voiceover }}</span>
          </div>
          <audio
            ref="audioRef"
            controls
            :src="playerAudio?.url || ''"
            @ended="$emit('audio-ended')"
          ></audio>
          <p v-if="!playerAudio" class="render-empty">No audio clip for this slide yet. Generate all clips first.</p>
          <div class="player-controls">
            <button type="button" class="secondary" :disabled="playerIndex === 0" @click="$emit('previous')">← Previous</button>
            <button type="button" class="primary" :disabled="!playerAudio" @click="$emit('play')">{{ playerPlaying ? 'Replay clip' : 'Play clip' }}</button>
            <button type="button" class="secondary" :disabled="playerIndex >= slideCount - 1" @click="$emit('next')">Next →</button>
          </div>
          <label class="autoplay-toggle">
            <input :checked="autoAdvance" type="checkbox" @change="$emit('update:autoAdvance', $event.target.checked)" />
            Auto-advance when clip ends
          </label>
        </aside>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const audioRef = ref(null)

defineProps({
  playerIndex: { type: Number, default: 0 },
  slideCount: { type: Number, default: 0 },
  aspectRatio: { type: String, default: '16:9' },
  playerSlide: { type: Object, default: null },
  playerRender: { type: Object, default: null },
  playerBeat: { type: Object, default: null },
  playerAudio: { type: Object, default: null },
  playerPlaying: { type: Boolean, default: false },
  autoAdvance: { type: Boolean, default: false },
})

defineEmits(['close', 'previous', 'next', 'play', 'audio-ended', 'update:autoAdvance'])

defineExpose({ audioRef })
</script>

<style>
.timeline-player-modal {
  width: min(1180px, 94vw);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  background: #0d1117;
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
}
.timeline-player-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(360px, 1fr) 360px;
  gap: 1rem;
  padding: 1rem;
  overflow: auto;
}
.player-stage {
  min-height: 520px;
  display: grid;
  place-items: center;
  border: 1px solid #243244;
  border-radius: 14px;
  background: #020617;
  overflow: hidden;
}
.player-stage.vertical img { max-height: 76vh; max-width: min(430px, 100%); }
.player-stage img {
  display: block;
  max-width: 100%;
  max-height: 76vh;
  object-fit: contain;
}
.player-placeholder {
  display: grid;
  gap: 0.7rem;
  place-items: center;
  text-align: center;
  padding: 2rem;
  color: #cbd5e1;
}
.player-placeholder strong { color: #f8fafc; font-size: 1.2rem; }
.player-placeholder span { color: #94a3b8; }
.player-side {
  border: 1px solid #243244;
  border-radius: 14px;
  padding: 1rem;
  background: #081018;
  overflow: auto;
}
.player-side h3 { margin: 0.4rem 0 0.6rem; color: #f8fafc; }
.player-side p { color: #cbd5e1; line-height: 1.45; }
.player-side audio { width: 100%; margin-top: 0.8rem; }
.player-controls {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.9rem;
}
.player-controls button {
  padding: 0.45rem 0.75rem;
  border-radius: 6px;
  border: 1px solid #334155;
  cursor: pointer;
}
.player-controls .primary { background: #4ade80; color: #052e16; font-weight: 700; }
.player-controls .secondary { background: #111827; color: #dbeafe; }
.player-controls button:disabled { opacity: 0.45; cursor: not-allowed; }
.autoplay-toggle {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-top: 0.9rem;
  color: #94a3b8;
  font-size: 0.82rem;
}

@media (max-width: 900px) {
  .timeline-player-body { grid-template-columns: 1fr; }
  .player-stage { min-height: 360px; }
}
</style>
