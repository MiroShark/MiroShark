<template>
  <div class="foresight-overlay" @click.self="$emit('close')">
    <div class="infographic-modal">
      <header class="foresight-header">
        <div>
          <h2>Infographic timeline</h2>
          <p class="modal-subtitle">{{ infographicPlan?.slide_count || 0 }} timeline beats · {{ infographicPlan?.aspect_ratio || '16:9' }} · {{ infographicPlan?.output_format || 'landscape' }}</p>
          <p v-if="infographicAccounting" class="cost-subtitle">OpenAI today: {{ infographicAccounting.openai_used_today }}/{{ infographicAccounting.openai_daily_limit }} renders used · {{ infographicAccounting.openai_remaining_today }} left</p>
        </div>
        <div class="format-toggle" role="group" aria-label="Infographic format">
          <button type="button" :class="{ active: infographicFormat === 'landscape' }" @click="$emit('set-format', 'landscape')">16:9</button>
          <button type="button" :class="{ active: infographicFormat === 'tiktok' }" @click="$emit('set-format', 'tiktok')">TikTok 9:16</button>
        </div>
        <button type="button" class="close" @click="$emit('close')">×</button>
      </header>

      <div class="infographic-body">
        <aside class="slide-list timeline-list">
          <div class="timeline-heading">Story timeline</div>
          <button
            v-for="row in timelineRows"
            :key="row.slideKey"
            type="button"
            :class="['slide-tab', 'timeline-step', `depth-${row.depth}`, { active: selectedIndex === row.index, rendered: hasInfographicRender(row.index), chapter: row.depth === 0 }]"
            :style="{ '--depth': row.depth }"
            @click="$emit('select-slide', row.index)"
          >
            <span class="depth-rail" aria-hidden="true"></span>
            <span class="slide-number">{{ row.index + 1 }}</span>
            <span>
              <small class="timeline-chapter">{{ row.chapter }}</small>
              <strong>{{ row.slide.title }}</strong>
              <em>{{ row.slide.slide_type }}</em>
              <small v-if="narrationBeatFor(row.index)">{{ narrationBeatFor(row.index).duration_seconds }}s audio beat</small>
            </span>
          </button>
        </aside>

        <section v-if="selectedSlide" class="slide-preview">
          <div class="audio-block">
            <div class="prompt-header">
              <div>
                <h4>Narration audio</h4>
                <p class="audio-subtitle">Per-slide audio clips only. Local Piper is default; OmniVoice is optional later.</p>
              </div>
              <div class="audio-actions">
                <button type="button" class="secondary tiny" :disabled="planningNarration" @click="$emit('plan-narration')">{{ planningNarration ? 'Writing…' : (narrationScript ? 'Rewrite script' : 'Write script') }}</button>
                <button type="button" class="primary tiny" :disabled="renderingNarration || generatingAllSlideClips || !selectedNarrationBeat" @click="$emit('render-narration-audio')">{{ renderingNarration ? 'Generating clip…' : (currentSlideAudioRender ? 'Regenerate slide clip' : 'Generate slide clip') }}</button>
                <button type="button" class="secondary tiny" :disabled="generatingAllSlideClips || renderingNarration || !narrationScript" @click="$emit('generate-all-slide-clips')">{{ generatingAllSlideClips ? 'Generating all…' : 'Generate all clips' }}</button>
              </div>
            </div>
            <div class="audio-content">
              <div v-if="narrationScript" class="script-summary">
                <strong>{{ narrationScript.slides?.length || 0 }} narration beats</strong>
                <span>{{ narrationScript.estimated_duration_seconds || '—' }}s stitched total</span>
                <button type="button" class="secondary tiny" @click="$emit('copy-narration-script')">Copy script</button>
              </div>
              <div v-if="clipGenerationProgress.total" class="clip-progress">
                <strong>Clip generation</strong>
                <span>{{ clipGenerationProgress.current }}/{{ clipGenerationProgress.total }}</span>
                <em>{{ clipGenerationProgress.label }}</em>
              </div>
              <p v-if="clipGenerationError" class="clip-error">{{ clipGenerationError }}</p>
              <p v-if="!narrationScript" class="render-empty">No narration script yet. Write the script first, then generate audio.</p>
              <details v-if="narrationScript" class="script-details">
                <summary>View voiceover text</summary>
                <p>{{ narrationScript.full_voiceover }}</p>
              </details>
              <div v-if="currentSlideAudioRender" class="audio-result">
                <audio controls :src="currentSlideAudioRender.url"></audio>
                <a class="download-link" :href="currentSlideAudioRender.url" download>Download slide WAV</a>
                <span>Slide {{ selectedIndex + 1 }} · {{ currentSlideAudioRender.provider }} · {{ currentSlideAudioRender.bytes }} bytes</span>
              </div>
            </div>
          </div>

          <div class="slide-card-preview">
            <div class="slide-type">{{ selectedSlide.slide_type }}</div>
            <h3>{{ selectedSlide.title }}</h3>
            <p>{{ selectedSlide.message }}</p>
            <div v-if="selectedNarrationBeat" class="slide-narration-beat">
              <strong>Slide audio beat · {{ selectedNarrationBeat.duration_seconds }}s</strong>
              <span>{{ selectedNarrationBeat.voiceover }}</span>
            </div>
            <div class="label-row">
              <span v-for="label in selectedSlide.labels" :key="label">{{ label }}</span>
            </div>
            <ul>
              <li v-for="(fact, i) in selectedSlide.facts" :key="i">{{ fact.text }}</li>
            </ul>
          </div>

          <div class="render-block">
            <div class="prompt-header">
              <div>
                <h4>OpenAI GPT Image render</h4>
                <p class="audio-subtitle">Strict/simple reference mode is used for supported slides. Today: {{ infographicAccounting?.openai_used_today ?? '—' }}/{{ infographicAccounting?.openai_daily_limit ?? '—' }} renders used.</p>
              </div>
              <button type="button" class="primary tiny" :disabled="renderingInfographic || batchRenderingInfographics || infographicAccounting?.openai_remaining_today === 0" @click="$emit('render-selected-infographic')">{{ renderingInfographic ? 'Rendering…' : (infographicAccounting?.openai_remaining_today === 0 ? 'Budget used' : 'Render strict slide') }}</button>
              <button type="button" class="secondary tiny" :disabled="renderingInfographic || batchRenderingInfographics || !nextUnrenderedSlides.length || infographicAccounting?.openai_remaining_today === 0" @click="$emit('render-next-infographics')">{{ batchRenderingInfographics ? 'Rendering batch…' : `Render next ${nextUnrenderedSlides.length || 5}` }}</button>
            </div>
            <div v-if="batchRenderProgress.total" class="clip-progress render-progress">
              <strong>Image batch</strong>
              <span>{{ batchRenderProgress.current }}/{{ batchRenderProgress.total }}</span>
              <em>{{ batchRenderProgress.label }}</em>
            </div>
            <p v-if="batchRenderError" class="clip-error">{{ batchRenderError }}</p>
            <p v-if="infographicAccounting?.openai_remaining_today === 0" class="clip-error">OpenAI image daily limit reached. Raise OPENAI_IMAGE_DAILY_LIMIT or wait for reset.</p>
            <div v-if="currentInfographicRender" class="render-result">
              <img :src="currentInfographicRender.url" :alt="selectedSlide.title" />
              <p>{{ currentInfographicRender.model }} · {{ currentInfographicRender.aspect_ratio }} · {{ currentInfographicRender.bytes }} bytes</p>
            </div>
            <div v-else class="render-empty">No rendered image yet. Render this slide to call OpenAI GPT Image with the strict/simple template when available.</div>
          </div>

          <div class="prompt-block">
            <div class="prompt-header">
              <h4>OpenAI image API prompt</h4>
              <button type="button" class="secondary tiny" @click="$emit('copy-infographic-prompt')">Copy prompt</button>
            </div>
            <pre>{{ selectedSlide.image_prompt }}</pre>
          </div>
        </section>
      </div>

      <footer class="foresight-footer">
        <button type="button" class="secondary" @click="$emit('copy-infographic-json')">Copy JSON</button>
        <button type="button" class="secondary" @click="$emit('download-infographic-json')">Download JSON</button>
        <button type="button" class="primary" :disabled="planningInfographics" @click="$emit('regenerate-infographics')">Regenerate plan</button>
        <button type="button" class="secondary" :disabled="!infographicPlan" @click="$emit('open-timeline-player')">Play timeline ▶</button>
        <button type="button" class="secondary" @click="$emit('close')">Close</button>
      </footer>
    </div>
  </div>
</template>

<script setup>
defineProps({
  infographicPlan: { type: Object, default: null },
  infographicAccounting: { type: Object, default: null },
  infographicFormat: { type: String, default: 'landscape' },
  timelineRows: { type: Array, default: () => [] },
  selectedIndex: { type: Number, default: 0 },
  selectedSlide: { type: Object, default: null },
  planningNarration: { type: Boolean, default: false },
  narrationScript: { type: Object, default: null },
  renderingNarration: { type: Boolean, default: false },
  generatingAllSlideClips: { type: Boolean, default: false },
  selectedNarrationBeat: { type: Object, default: null },
  currentSlideAudioRender: { type: Object, default: null },
  clipGenerationProgress: { type: Object, default: () => ({}) },
  clipGenerationError: { type: String, default: '' },
  renderingInfographic: { type: Boolean, default: false },
  batchRenderingInfographics: { type: Boolean, default: false },
  nextUnrenderedSlides: { type: Array, default: () => [] },
  batchRenderProgress: { type: Object, default: () => ({}) },
  batchRenderError: { type: String, default: '' },
  currentInfographicRender: { type: Object, default: null },
  planningInfographics: { type: Boolean, default: false },
  hasInfographicRender: { type: Function, required: true },
  narrationBeatFor: { type: Function, required: true },
})

defineEmits([
  'close',
  'set-format',
  'select-slide',
  'plan-narration',
  'render-narration-audio',
  'generate-all-slide-clips',
  'copy-narration-script',
  'render-selected-infographic',
  'render-next-infographics',
  'copy-infographic-prompt',
  'copy-infographic-json',
  'download-infographic-json',
  'regenerate-infographics',
  'open-timeline-player',
])
</script>

<style>
.format-toggle {
  display: inline-flex;
  gap: 0.25rem;
  padding: 0.2rem;
  border: 1px solid #334155;
  border-radius: 999px;
  background: #0b1016;
}
.format-toggle button {
  border: 0;
  border-radius: 999px;
  padding: 0.3rem 0.65rem;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.78rem;
}
.format-toggle button.active {
  background: #2563eb;
  color: white;
}

.infographic-modal {
  width: min(1180px, 94vw);
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  background: #0d1117;
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
}
.cost-subtitle {
  margin: 0.2rem 0 0;
  color: #fbbf24;
  font-size: 0.75rem;
}

.modal-subtitle {
  margin: 0.25rem 0 0;
  color: #94a3b8;
  font-size: 0.8rem;
}
.infographic-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 320px 1fr;
  overflow: hidden;
}
.slide-list {
  overflow-y: auto;
  border-right: 1px solid #1f2937;
  padding: 0.75rem;
  background: #0b1016;
}
.timeline-heading {
  position: sticky;
  top: 0;
  z-index: 2;
  margin: -0.75rem -0.75rem 0.75rem;
  padding: 0.75rem;
  border-bottom: 1px solid #1f2937;
  background: #0b1016;
  color: #f8fafc;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.timeline-list { position: relative; }
.timeline-list::before {
  content: "";
  position: absolute;
  left: 1.55rem;
  top: 4rem;
  bottom: 1rem;
  width: 2px;
  background: linear-gradient(#60a5fa, #f59e0b, #4ade80);
  opacity: 0.45;
}
.slide-tab {
  position: relative;
  width: 100%;
  display: grid;
  grid-template-columns: 0.35rem 2rem 1fr;
  gap: 0.65rem;
  text-align: left;
  padding: 0.65rem 0.65rem 0.65rem calc(0.65rem + (var(--depth, 0) * 1.25rem));
  margin-bottom: 0.5rem;
  border: 1px solid #243244;
  border-radius: 10px;
  background: #111827;
  color: #d1d5db;
  cursor: pointer;
}
.slide-tab.depth-1 { background: #0f1a27; }
.slide-tab.depth-2 { background: #111b20; border-style: dashed; }
.slide-tab.depth-3 { background: #111714; border-style: dotted; }
.slide-tab.chapter { border-color: #36506d; }
.depth-rail {
  width: 0.25rem;
  min-height: 100%;
  border-radius: 999px;
  background: #334155;
}
.slide-tab.depth-0 .depth-rail { background: #60a5fa; }
.slide-tab.depth-1 .depth-rail { background: #f59e0b; }
.slide-tab.depth-2 .depth-rail { background: #4ade80; }
.slide-tab.depth-3 .depth-rail { background: #a78bfa; }
.timeline-step { box-shadow: 0 0 0 3px #0b1016; }
.timeline-step.rendered { border-color: #315a46; }
.slide-tab.active { border-color: #60a5fa; background: #102033; }
.slide-tab strong { display: block; font-size: 0.82rem; line-height: 1.25; }
.slide-tab em { display: block; margin-top: 0.2rem; color: #8aa0b6; font-size: 0.72rem; font-style: normal; }
.slide-tab small { display: block; margin-top: 0.25rem; color: #fbbf24; font-size: 0.68rem; }
.timeline-chapter {
  margin: 0 0 0.15rem;
  color: #93c5fd !important;
  font-size: 0.62rem !important;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.slide-number {
  position: relative;
  z-index: 1;
  width: 1.6rem;
  height: 1.6rem;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #1e293b;
  color: #bfdbfe;
  border: 1px solid #36506d;
  font-weight: 700;
  font-size: 0.75rem;
}
.slide-tab.active .slide-number { background: #2563eb; color: white; }
.slide-preview {
  overflow-y: auto;
  padding: 1rem;
}
.slide-card-preview {
  border: 1px solid #2c3f55;
  border-radius: 12px;
  padding: 1rem;
  background: linear-gradient(135deg, #111827, #0f172a);
}
.slide-type {
  color: #93c5fd;
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.slide-card-preview h3 { margin: 0.35rem 0 0.5rem; color: #f8fafc; }
.slide-card-preview p { color: #cbd5e1; line-height: 1.45; }
.label-row { display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0.75rem 0; }
.label-row span {
  border: 1px solid #334155;
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  color: #dbeafe;
  background: #132033;
  font-size: 0.75rem;
}
.slide-card-preview li { margin: 0.35rem 0; color: #d1d5db; }
.slide-narration-beat {
  margin: 0.75rem 0;
  padding: 0.75rem;
  border: 1px solid #315179;
  border-radius: 10px;
  background: #0b1b2b;
}
.slide-narration-beat strong {
  display: block;
  color: #bfdbfe;
  font-size: 0.75rem;
  margin-bottom: 0.35rem;
}
.slide-narration-beat span {
  display: block;
  color: #e5e7eb;
  line-height: 1.45;
  font-size: 0.86rem;
}

.render-block {
  margin-top: 1rem;
  border: 1px solid #243244;
  border-radius: 10px;
  overflow: hidden;
  background: #081018;
}
.render-result { padding: 0.85rem; }
.render-result img {
  display: block;
  width: 100%;
  max-height: 520px;
  object-fit: contain;
  border-radius: 8px;
  background: #020617;
}
.render-result p { margin: 0.5rem 0 0; color: #94a3b8; font-size: 0.75rem; }
.render-empty {
  padding: 0.9rem;
  color: #94a3b8;
  font-size: 0.82rem;
  font-style: italic;
}

.audio-block {
  margin-bottom: 1rem;
  border: 1px solid #29405a;
  border-radius: 10px;
  overflow: hidden;
  background: #081018;
}
.audio-subtitle {
  margin: 0.2rem 0 0;
  color: #94a3b8;
  font-size: 0.74rem;
}
.audio-actions {
  display: flex;
  gap: 0.45rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.audio-content {
  padding: 0.85rem;
}
.script-summary {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
  color: #dbeafe;
  font-size: 0.82rem;
}
.script-summary span { color: #94a3b8; }
.clip-progress {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
  margin-top: 0.75rem;
  padding: 0.55rem 0.65rem;
  border: 1px solid #315a72;
  border-radius: 8px;
  background: #0f2635;
  color: #d7efff;
  font-size: 0.78rem;
}
.clip-progress span { color: #fbbf24; }
.clip-progress em { color: #94a3b8; font-style: normal; }
.clip-error {
  margin: 0.65rem 0 0;
  padding: 0.6rem 0.7rem;
  border: 1px solid #7f3f46;
  border-radius: 8px;
  background: #32151a;
  color: #fecaca;
  font-size: 0.78rem;
}

.script-details {
  margin-top: 0.7rem;
  color: #cbd5e1;
  font-size: 0.8rem;
}
.script-details summary { cursor: pointer; color: #93c5fd; }
.script-details p {
  line-height: 1.5;
  color: #cbd5e1;
}
.audio-result {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  flex-wrap: wrap;
  margin-top: 0.8rem;
  color: #94a3b8;
  font-size: 0.78rem;
}
.audio-result audio { min-width: min(100%, 420px); }
.download-link {
  color: #bfdbfe;
  text-decoration: none;
  border: 1px solid #315179;
  border-radius: 999px;
  padding: 0.3rem 0.6rem;
  background: #102033;
}
.download-link:hover { background: #17304d; }

.prompt-block {
  margin-top: 1rem;
  border: 1px solid #243244;
  border-radius: 10px;
  overflow: hidden;
  background: #0b1016;
}
.prompt-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 0.65rem 0.8rem;
  border-bottom: 1px solid #1f2937;
}
.prompt-header h4 { margin: 0; font-size: 0.85rem; color: #e5e7eb; }
.prompt-block pre {
  margin: 0;
  padding: 0.85rem;
  white-space: pre-wrap;
  color: #cbd5e1;
  font-size: 0.78rem;
  line-height: 1.45;
  max-height: 330px;
  overflow: auto;
}

</style>
