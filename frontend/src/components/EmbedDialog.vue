<template>
  <Teleport to="body">
    <Transition name="embed-dialog">
      <div v-if="open" class="embed-dialog-overlay" @click.self="$emit('close')">
        <div class="embed-dialog">
          <!-- Header -->
          <div class="embed-dialog-header">
            <div class="embed-dialog-title">
              <span class="title-icon">⌘</span>
              <span>Embed simulation</span>
              <span class="title-sub">{{ formatSimulationId(simulationId) }}</span>
            </div>
            <button class="embed-dialog-close" @click="$emit('close')">×</button>
          </div>

          <!-- Description -->
          <p class="embed-dialog-desc">
            Paste the iframe below into Notion, Substack, Medium, a GitHub README, or any HTML page.
            The widget loads live from this MiroShark instance and updates automatically as the simulation changes.
          </p>

          <!-- Public toggle -->
          <div class="embed-public-row">
            <label class="embed-public-toggle">
              <input type="checkbox" :checked="isPublic" @change="togglePublic" :disabled="publishing" />
              <span class="embed-public-label">
                {{ isPublic ? 'Public — embeddable by anyone with the URL' : 'Private — embed URL returns 403' }}
              </span>
            </label>
            <span v-if="publishError" class="embed-public-error">{{ publishError }}</span>
          </div>

          <!-- Size presets -->
          <div class="embed-size-row">
            <span class="embed-size-label">Size</span>
            <div class="embed-size-buttons">
              <button
                v-for="preset in sizePresets"
                :key="preset.name"
                class="embed-size-btn"
                :class="{ active: activePreset === preset.name }"
                @click="activePreset = preset.name"
              >
                {{ preset.name }}
                <span class="embed-size-dim">{{ preset.width }}×{{ preset.height }}</span>
              </button>
            </div>
            <label class="embed-theme-toggle">
              <span>Theme</span>
              <select v-model="theme" class="embed-theme-select">
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </label>
          </div>

          <!-- Preview -->
          <div class="embed-preview-wrap" :class="`preview-${activePreset.toLowerCase()}`">
            <div class="embed-preview-frame" :style="previewStyle">
              <iframe
                v-if="embedUrl"
                :src="embedUrl"
                :style="iframeStyle"
                frameborder="0"
                loading="lazy"
                title="MiroShark simulation embed preview"
              ></iframe>
            </div>
          </div>

          <!-- Copyable snippets -->
          <div class="embed-snippets">
            <div class="snippet-block">
              <div class="snippet-head">
                <span class="snippet-label">HTML iframe</span>
                <button class="snippet-copy-btn" @click="copy('iframe')">
                  {{ copied === 'iframe' ? '✓ Copied' : 'Copy' }}
                </button>
              </div>
              <pre class="snippet-code"><code>{{ iframeSnippet }}</code></pre>
            </div>

            <div class="snippet-block">
              <div class="snippet-head">
                <span class="snippet-label">Markdown (Notion / Substack auto-embed)</span>
                <button class="snippet-copy-btn" @click="copy('markdown')">
                  {{ copied === 'markdown' ? '✓ Copied' : 'Copy' }}
                </button>
              </div>
              <pre class="snippet-code"><code>{{ markdownSnippet }}</code></pre>
            </div>

            <div class="snippet-block">
              <div class="snippet-head">
                <span class="snippet-label">Direct URL</span>
                <button class="snippet-copy-btn" @click="copy('url')">
                  {{ copied === 'url' ? '✓ Copied' : 'Copy' }}
                </button>
              </div>
              <pre class="snippet-code"><code>{{ embedUrl }}</code></pre>
            </div>
          </div>

          <!-- Social share card -->
          <div class="share-card-section">
            <div class="share-card-divider">
              <span class="divider-line"></span>
              <span class="divider-text">Social card</span>
              <span class="divider-line"></span>
            </div>

            <p class="share-card-desc">
              A 1200×630 PNG with the scenario headline, status, quality, and
              belief split — the same image Twitter/X, Discord, Slack, and
              LinkedIn unfurl automatically when someone pastes the share
              link.
            </p>

            <div class="share-card-preview-wrap">
              <img
                v-if="isPublic && shareCardUrl"
                :src="shareCardUrl"
                :key="shareCardCacheBust"
                class="share-card-preview"
                alt="MiroShark share card preview"
                @error="onShareCardError"
              />
              <div v-else class="share-card-empty">
                {{ isPublic ? 'Loading preview…' : 'Publish the simulation to enable the share card.' }}
              </div>
            </div>

            <div class="share-card-actions">
              <div class="snippet-block share-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">Share link (auto-unfurls with card)</span>
                  <button class="snippet-copy-btn" @click="copy('share')" :disabled="!isPublic">
                    {{ copied === 'share' ? '✓ Copied' : 'Copy link' }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ shareLandingUrl || '—' }}</code></pre>
              </div>

              <div class="snippet-block share-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">Card image URL (for manual paste)</span>
                  <button class="snippet-copy-btn" @click="copy('card')" :disabled="!isPublic">
                    {{ copied === 'card' ? '✓ Copied' : 'Copy URL' }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ shareCardUrl || '—' }}</code></pre>
              </div>

              <a
                v-if="isPublic && shareCardUrl"
                class="share-download-btn"
                :href="shareCardUrl"
                :download="`miroshark-${simulationId.slice(0, 12)}.png`"
              >
                ↓ Download PNG
              </a>
            </div>

            <!-- Animated belief replay — same 1200×630 frame as the share
                 card but one frame per round, so X / Discord / Slack
                 auto-play the belief drift inline. -->
            <div class="replay-section">
              <div class="replay-head">
                <span class="replay-icon">▶</span>
                <div class="replay-head-body">
                  <div class="replay-title">Belief replay (animated)</div>
                  <div class="replay-sub">
                    Same canvas as the share card, one frame per round.
                    Discord and Slack auto-play GIFs from the direct URL —
                    drop the link in a channel and it plays inline.
                  </div>
                </div>
              </div>

              <div
                v-if="isPublic && replayGifUrl"
                class="replay-preview-wrap"
                :class="{ 'replay-preview-paused': !replayPlay }"
                @click="startReplay"
              >
                <img
                  v-if="replayPlay"
                  :src="replayGifUrl"
                  class="replay-preview"
                  :class="{ 'replay-preview-loaded': replayLoaded }"
                  alt="MiroShark belief replay GIF"
                  @load="onReplayLoad"
                  @error="onReplayError"
                />
                <div v-if="!replayPlay" class="replay-overlay">
                  <span class="replay-overlay-icon">▶</span>
                  <span class="replay-overlay-text">Tap to play</span>
                </div>
              </div>
              <div v-else class="replay-empty">
                Publish the simulation to enable the belief replay GIF.
              </div>

              <div class="replay-actions">
                <div class="snippet-block share-snippet">
                  <div class="snippet-head">
                    <span class="snippet-label">Replay GIF URL (auto-plays in Discord / Slack)</span>
                    <button
                      class="snippet-copy-btn"
                      @click="copy('replay')"
                      :disabled="!isPublic"
                    >
                      {{ copied === 'replay' ? '✓ Copied' : 'Copy URL' }}
                    </button>
                  </div>
                  <pre class="snippet-code"><code>{{ replayGifUrl || '—' }}</code></pre>
                </div>

                <a
                  v-if="isPublic && replayGifUrl"
                  class="share-download-btn"
                  :href="replayGifUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-replay.gif`"
                >
                  ↓ Download GIF
                </a>
              </div>
            </div>

            <!-- Text transcript — pairs with the share card (preview)
                 and replay GIF (motion) as the third quote-friendly
                 share format. The Markdown form has YAML front matter
                 so Notion / Obsidian / Bear / Substack pick it up as
                 page metadata; the JSON form is for SDK consumers. -->
            <div class="transcript-section">
              <div class="transcript-head">
                <span class="transcript-icon">📄</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">Export transcript</div>
                  <div class="transcript-sub">
                    Per-round agent posts + stance labels + final
                    consensus. Cite the simulation in a research paper
                    or a Substack post without screenshotting.
                  </div>
                </div>
              </div>

              <div class="transcript-actions">
                <a
                  v-if="isPublic && transcriptMarkdownUrl"
                  class="transcript-download-btn"
                  :href="transcriptMarkdownUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-transcript.md`"
                >
                  ↓ Download .md
                </a>
                <a
                  v-if="isPublic && transcriptJsonUrl"
                  class="transcript-download-btn transcript-download-btn-secondary"
                  :href="transcriptJsonUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-transcript.json`"
                >
                  ↓ Download .json
                </a>
                <span v-if="!isPublic" class="transcript-empty">
                  Publish the simulation to enable the transcript export.
                </span>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">Markdown URL (Notion / Obsidian "Import from URL")</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('transcriptMd')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'transcriptMd' ? '✓ Copied' : 'Copy URL' }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ transcriptMarkdownUrl || '—' }}</code></pre>
              </div>
            </div>

            <!-- Verified-prediction annotation — lets operators turn a
                 published simulation into a "called it" record on the
                 /verified gallery page. Only meaningful once the run is
                 public, so the inputs are disabled until then. -->
            <div class="outcome-section" :class="{ 'outcome-section-live': isPublic }">
              <div class="outcome-head">
                <span class="outcome-icon">📍</span>
                <div class="outcome-head-body">
                  <div class="outcome-title">
                    Mark outcome
                    <span v-if="outcome && outcome.label" class="outcome-saved-tag">
                      ✓ {{ outcomeLabelText(outcome.label) }}
                    </span>
                  </div>
                  <div class="outcome-sub">
                    Did this simulation predict a real event? Annotate it and
                    your run lands on
                    <a href="/verified" target="_blank" rel="noopener">/verified</a>
                    — the public hall of calls that landed.
                  </div>
                </div>
              </div>

              <div class="outcome-fields" :class="{ 'outcome-fields-disabled': !isPublic }">
                <fieldset class="outcome-radio-group" :disabled="!isPublic">
                  <label
                    v-for="opt in outcomeOptions"
                    :key="opt.value"
                    class="outcome-radio"
                    :class="{ 'outcome-radio-active': outcomeForm.label === opt.value }"
                  >
                    <input
                      type="radio"
                      :value="opt.value"
                      v-model="outcomeForm.label"
                    />
                    <span class="outcome-radio-icon">{{ opt.icon }}</span>
                    <span class="outcome-radio-label">{{ opt.label }}</span>
                  </label>
                </fieldset>

                <input
                  v-model="outcomeForm.outcome_url"
                  type="url"
                  placeholder="Outcome URL (article, tweet, dashboard) — optional"
                  class="outcome-input"
                  :disabled="!isPublic"
                  maxlength="500"
                />
                <textarea
                  v-model="outcomeForm.outcome_summary"
                  placeholder="What happened, in one or two sentences (max 280 chars)"
                  class="outcome-textarea"
                  :disabled="!isPublic"
                  maxlength="280"
                  rows="2"
                ></textarea>
                <div class="outcome-summary-counter">
                  {{ outcomeForm.outcome_summary.length }}/280
                </div>

                <div class="outcome-actions">
                  <button
                    class="outcome-submit"
                    @click="submitOutcome"
                    :disabled="!isPublic || !outcomeForm.label || outcomeSubmitting"
                  >
                    <span v-if="outcomeSubmitting">Saving…</span>
                    <span v-else-if="outcome">Update outcome</span>
                    <span v-else>Save outcome</span>
                  </button>
                  <a
                    v-if="outcome"
                    href="/verified"
                    target="_blank"
                    rel="noopener"
                    class="outcome-link"
                  >
                    View on /verified ↗
                  </a>
                </div>

                <div v-if="outcomeMessage" class="outcome-message" :class="outcomeMessageClass">
                  {{ outcomeMessage }}
                </div>
              </div>
            </div>

            <!-- Gallery callout — appears once the simulation is public so the
                 operator knows their run is visible on /explore, and offers a
                 one-click jump to see it in situ alongside other public runs. -->
            <div class="gallery-callout" :class="{ 'gallery-callout-live': isPublic }">
              <div class="gallery-callout-icon">◎</div>
              <div class="gallery-callout-body">
                <div class="gallery-callout-title">
                  {{ isPublic ? 'Live on the public gallery' : 'Submit to the public gallery' }}
                </div>
                <div class="gallery-callout-desc">
                  <template v-if="isPublic">
                    This simulation is now visible on
                    <a href="/explore" target="_blank" rel="noopener">/explore</a> —
                    the public gallery where anyone can browse published runs
                    and fork them into their own simulations.
                  </template>
                  <template v-else>
                    Toggle "Public" above and this run joins the community
                    gallery at
                    <a href="/explore" target="_blank" rel="noopener">/explore</a>.
                    Others can browse it, view the full belief drift, and
                    fork your agents into their own scenarios.
                  </template>
                </div>
              </div>
              <a
                v-if="isPublic"
                href="/explore"
                target="_blank"
                rel="noopener"
                class="gallery-callout-link"
              >
                Open gallery ↗
              </a>
            </div>
          </div>

          <!-- Hint -->
          <div class="embed-dialog-hint">
            <span class="hint-icon">ⓘ</span>
            The widget reads from this instance's API, so viewers must be able to reach
            <code>{{ origin }}</code>. For public embeds, deploy MiroShark somewhere reachable from the internet.
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { reactive, ref, computed, watch } from 'vue'
import {
  publishSimulation,
  getEmbedSummary,
  getShareCardUrl,
  getReplayGifUrl,
  getShareLandingUrl,
  getTranscriptMarkdownUrl,
  getTranscriptJsonUrl,
  getSimulationOutcome,
  submitSimulationOutcome,
} from '../api/simulation'

const props = defineProps({
  open: { type: Boolean, default: false },
  simulationId: { type: String, required: true },
  initialPublic: { type: Boolean, default: false }
})

defineEmits(['close'])

const isPublic = ref(props.initialPublic)
const publishing = ref(false)
const publishError = ref('')

const togglePublic = async () => {
  const next = !isPublic.value
  publishing.value = true
  publishError.value = ''
  try {
    const res = await publishSimulation(props.simulationId, next)
    isPublic.value = res?.data?.is_public ?? next
  } catch (err) {
    publishError.value = err?.response?.data?.error || err?.message || 'Publish failed'
  } finally {
    publishing.value = false
  }
}

const sizePresets = [
  { name: 'Compact', width: 480, height: 260 },
  { name: 'Standard', width: 640, height: 340 },
  { name: 'Wide', width: 800, height: 420 }
]

const activePreset = ref('Standard')
const theme = ref('light')
const copied = ref('')

const origin = computed(() => {
  if (typeof window === 'undefined') return ''
  return window.location.origin
})

const currentSize = computed(() => {
  return sizePresets.find(p => p.name === activePreset.value) || sizePresets[1]
})

const embedUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  const base = `${origin.value}/embed/${props.simulationId}`
  const params = new URLSearchParams()
  if (theme.value !== 'light') params.set('theme', theme.value)
  const query = params.toString()
  return query ? `${base}?${query}` : base
})

const iframeSnippet = computed(() => {
  const { width, height } = currentSize.value
  return `<iframe src="${embedUrl.value}" width="${width}" height="${height}" frameborder="0" loading="lazy" title="MiroShark simulation"></iframe>`
})

const markdownSnippet = computed(() => {
  if (!embedUrl.value) return ''
  return `[MiroShark simulation ↗](${embedUrl.value})`
})

const shareCardCacheBust = ref(0)

const shareCardUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  // Append a cache-bust token so re-opening the dialog after a state change
  // (e.g. resolution recorded) shows the freshly rendered card.
  const base = getShareCardUrl(props.simulationId, origin.value)
  return shareCardCacheBust.value
    ? `${base}?v=${shareCardCacheBust.value}`
    : base
})

const shareLandingUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getShareLandingUrl(props.simulationId, origin.value)
})

const replayGifUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  // Same cache-bust token as the share card so re-opens after a state
  // change pull the freshly rendered GIF instead of the stale cache.
  const base = getReplayGifUrl(props.simulationId, origin.value)
  return shareCardCacheBust.value
    ? `${base}?v=${shareCardCacheBust.value}`
    : base
})

const transcriptMarkdownUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getTranscriptMarkdownUrl(props.simulationId, origin.value)
})

const transcriptJsonUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getTranscriptJsonUrl(props.simulationId, origin.value)
})

const replayLoaded = ref(false)
const replayPlay = ref(false)
const onReplayLoad = () => {
  replayLoaded.value = true
}
const onReplayError = () => {
  // Image fails until the simulation publishes — the watch on isPublic
  // busts the cache once the operator toggles public on.
  replayLoaded.value = false
}
const startReplay = () => {
  replayPlay.value = true
}

const onShareCardError = () => {
  // The image fails until the simulation is published; once the operator
  // toggles public on, watch(isPublic) below busts the cache.
}

const previewStyle = computed(() => {
  const { width, height } = currentSize.value
  return {
    maxWidth: `${width}px`,
    aspectRatio: `${width} / ${height}`
  }
})

const iframeStyle = computed(() => ({
  width: '100%',
  height: '100%',
  border: 'none',
  borderRadius: '8px'
}))

const formatSimulationId = (id) => {
  if (!id) return ''
  const prefix = id.replace(/^sim_/, '').slice(0, 6)
  return `SIM_${prefix.toUpperCase()}`
}

const copy = async (which) => {
  let text = ''
  if (which === 'iframe') text = iframeSnippet.value
  else if (which === 'markdown') text = markdownSnippet.value
  else if (which === 'url') text = embedUrl.value
  else if (which === 'share') text = shareLandingUrl.value
  else if (which === 'card') text = shareCardUrl.value
  else if (which === 'replay') text = replayGifUrl.value
  else if (which === 'transcriptMd') text = transcriptMarkdownUrl.value
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copied.value = which
    setTimeout(() => {
      if (copied.value === which) copied.value = ''
    }, 1800)
  } catch (err) {
    // Fallback: select-able textarea
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    try { document.execCommand('copy') } catch (_) {}
    document.body.removeChild(ta)
    copied.value = which
    setTimeout(() => {
      if (copied.value === which) copied.value = ''
    }, 1800)
  }
}

// ── Verified-prediction outcome submission ─────────────────────────────
const outcomeOptions = [
  { value: 'correct', label: 'Called it', icon: '📍' },
  { value: 'partial', label: 'Partial', icon: '◑' },
  { value: 'incorrect', label: 'Called wrong', icon: '⚠' },
]

const outcomeForm = reactive({
  label: '',
  outcome_url: '',
  outcome_summary: '',
})

const outcome = ref(null)
const outcomeSubmitting = ref(false)
const outcomeMessage = ref('')
const outcomeMessageClass = ref('')

const outcomeLabelText = (label) => {
  const opt = outcomeOptions.find((o) => o.value === label)
  return opt ? opt.label : label || ''
}

const _applyOutcomeToForm = (data) => {
  outcome.value = data || null
  if (data && data.label) {
    outcomeForm.label = data.label
    outcomeForm.outcome_url = data.outcome_url || ''
    outcomeForm.outcome_summary = data.outcome_summary || ''
  }
}

const _resetOutcomeForm = () => {
  outcomeForm.label = ''
  outcomeForm.outcome_url = ''
  outcomeForm.outcome_summary = ''
  outcome.value = null
  outcomeMessage.value = ''
  outcomeMessageClass.value = ''
}

const loadOutcome = async () => {
  try {
    const res = await getSimulationOutcome(props.simulationId)
    _applyOutcomeToForm(res?.data || null)
  } catch (err) {
    // 404 here means the simulation doesn't exist yet — surface nothing.
    outcome.value = null
  }
}

const submitOutcome = async () => {
  if (!isPublic.value || !outcomeForm.label) return
  outcomeSubmitting.value = true
  outcomeMessage.value = ''
  try {
    const res = await submitSimulationOutcome(props.simulationId, {
      label: outcomeForm.label,
      outcome_url: outcomeForm.outcome_url.trim(),
      outcome_summary: outcomeForm.outcome_summary.trim(),
    })
    if (res?.success && res.data) {
      _applyOutcomeToForm(res.data)
      outcomeMessage.value =
        'Outcome saved — your simulation is visible in the Verified filter.'
      outcomeMessageClass.value = 'outcome-message-success'
    } else {
      outcomeMessage.value = res?.error || 'Could not save outcome.'
      outcomeMessageClass.value = 'outcome-message-error'
    }
  } catch (err) {
    outcomeMessage.value =
      err?.response?.data?.error || err?.message || 'Could not save outcome.'
    outcomeMessageClass.value = 'outcome-message-error'
  } finally {
    outcomeSubmitting.value = false
  }
}

watch(() => props.open, async (val) => {
  if (!val) return
  copied.value = ''
  // Reset the replay back to its paused poster state so each open
  // starts with a click-to-play affordance instead of immediately
  // pulling the GIF (which can be a few hundred KB).
  replayPlay.value = false
  replayLoaded.value = false
  _resetOutcomeForm()
  // Refresh public state when reopened — reflects external flips.
  try {
    const res = await getEmbedSummary(props.simulationId)
    if (typeof res?.data?.is_public === 'boolean') isPublic.value = res.data.is_public
  } catch (err) {
    if (err?.response?.status === 403) isPublic.value = false
  }
  // Always pull the saved outcome — the GET endpoint is publish-gate-free
  // so even private sims will reflect a previously recorded annotation.
  await loadOutcome()
  // Bust the share-card image cache so the preview reloads with whatever
  // state the simulation is in right now (resolution may have landed
  // since the dialog was last opened).
  shareCardCacheBust.value = Date.now()
})

// When the operator toggles public on, the share-card endpoint flips from
// 403 → 200. Bust the cache so the <img> retries instead of staying broken.
watch(isPublic, () => {
  shareCardCacheBust.value = Date.now()
})
</script>

<style scoped>
.embed-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 10, 10, 0.55);
  backdrop-filter: blur(4px);
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  overflow-y: auto;
}

.embed-dialog {
  background: #ffffff;
  color: #0a0a0a;
  width: min(720px, 100%);
  max-height: calc(100vh - 40px);
  overflow-y: auto;
  border-radius: 14px;
  border: 1px solid rgba(10, 10, 10, 0.08);
  box-shadow: 0 24px 56px rgba(0, 0, 0, 0.25);
  padding: 22px 24px 20px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.embed-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.embed-dialog-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.005em;
}

.title-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: rgba(234, 88, 12, 0.12);
  color: #ea580c;
  font-size: 13px;
}

.title-sub {
  font-size: 11px;
  font-weight: 500;
  color: #6b6b6b;
  letter-spacing: 0.04em;
  padding: 2px 8px;
  background: rgba(10, 10, 10, 0.04);
  border-radius: 999px;
}

.embed-dialog-close {
  background: transparent;
  border: none;
  font-size: 24px;
  line-height: 1;
  color: #6b6b6b;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.15s, color 0.15s;
}

.embed-dialog-close:hover {
  background: rgba(10, 10, 10, 0.05);
  color: #0a0a0a;
}

.embed-dialog-desc {
  font-size: 13px;
  color: #4b4b4b;
  margin: 6px 0 14px;
  line-height: 1.5;
}

.embed-size-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.embed-size-label {
  font-size: 12px;
  color: #6b6b6b;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.embed-size-buttons {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.embed-size-btn {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 6px 12px;
  border: 1px solid rgba(10, 10, 10, 0.12);
  background: #ffffff;
  color: #0a0a0a;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.15s;
}

.embed-size-btn:hover {
  border-color: rgba(10, 10, 10, 0.3);
}

.embed-size-btn.active {
  background: #0a0a0a;
  color: #ffffff;
  border-color: #0a0a0a;
}

.embed-size-dim {
  font-size: 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: 0.04em;
  opacity: 0.7;
}

.embed-theme-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  font-size: 12px;
  color: #6b6b6b;
  font-weight: 500;
}

.embed-theme-select {
  background: #ffffff;
  color: #0a0a0a;
  border: 1px solid rgba(10, 10, 10, 0.12);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
}

.embed-preview-wrap {
  background: repeating-linear-gradient(
    45deg,
    rgba(10, 10, 10, 0.03),
    rgba(10, 10, 10, 0.03) 10px,
    rgba(10, 10, 10, 0.06) 10px,
    rgba(10, 10, 10, 0.06) 20px
  );
  border: 1px solid rgba(10, 10, 10, 0.08);
  border-radius: 10px;
  padding: 14px;
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
}

.embed-preview-frame {
  width: 100%;
  background: #ffffff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
}

.embed-snippets {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.snippet-block {
  border: 1px solid rgba(10, 10, 10, 0.08);
  border-radius: 10px;
  overflow: hidden;
  background: rgba(10, 10, 10, 0.02);
}

.snippet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(10, 10, 10, 0.04);
  font-size: 11px;
  font-weight: 600;
  color: #6b6b6b;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.snippet-copy-btn {
  background: #0a0a0a;
  color: #ffffff;
  border: none;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.04em;
  transition: opacity 0.15s;
}

.snippet-copy-btn:hover { opacity: 0.85; }

.snippet-code {
  margin: 0;
  padding: 10px 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11.5px;
  line-height: 1.55;
  color: #1f1f1f;
  white-space: pre-wrap;
  word-break: break-all;
  background: transparent;
  max-height: 120px;
  overflow-y: auto;
}

.embed-dialog-hint {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(234, 88, 12, 0.06);
  border: 1px solid rgba(234, 88, 12, 0.2);
  border-radius: 8px;
  font-size: 12px;
  color: #4b4b4b;
  line-height: 1.5;
}

.hint-icon {
  flex-shrink: 0;
  color: #ea580c;
  font-weight: 700;
}

.embed-dialog-hint code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  padding: 1px 6px;
  background: rgba(10, 10, 10, 0.06);
  border-radius: 4px;
  font-size: 11px;
}

.share-card-section {
  margin-top: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.share-card-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #6b6b6b;
}

.share-card-divider .divider-line {
  flex: 1;
  height: 1px;
  background: rgba(10, 10, 10, 0.08);
}

.share-card-divider .divider-text {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.share-card-desc {
  font-size: 12.5px;
  color: #4b4b4b;
  margin: 0;
  line-height: 1.55;
}

.share-card-preview-wrap {
  background: repeating-linear-gradient(
    45deg,
    rgba(10, 10, 10, 0.03),
    rgba(10, 10, 10, 0.03) 10px,
    rgba(10, 10, 10, 0.06) 10px,
    rgba(10, 10, 10, 0.06) 20px
  );
  border: 1px solid rgba(10, 10, 10, 0.08);
  border-radius: 10px;
  padding: 14px;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 140px;
}

.share-card-preview {
  width: 100%;
  max-width: 560px;
  aspect-ratio: 1200 / 630;
  border-radius: 8px;
  background: #fafafa;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
  object-fit: contain;
  display: block;
}

.share-card-empty {
  color: #6b6b6b;
  font-size: 13px;
  text-align: center;
  padding: 24px 18px;
  line-height: 1.55;
}

.share-card-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.share-snippet {
  margin: 0;
}

.share-download-btn {
  display: inline-flex;
  align-self: flex-start;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: #0a0a0a;
  color: #ffffff;
  text-decoration: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: background 0.15s;
}

.share-download-btn:hover {
  background: #2a2a2a;
}

.replay-section {
  margin-top: 18px;
  padding: 14px 16px;
  background: #0a0a0a;
  color: #fafafa;
  border-radius: 10px;
  border: 1px solid rgba(250, 250, 250, 0.08);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.replay-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.replay-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(234, 88, 12, 0.18);
  color: #ea580c;
  font-size: 11px;
  flex-shrink: 0;
  margin-top: 2px;
}

.replay-head-body {
  flex: 1;
  min-width: 0;
}

.replay-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #fafafa;
  margin-bottom: 4px;
}

.replay-sub {
  font-size: 12px;
  line-height: 1.5;
  color: rgba(250, 250, 250, 0.65);
}

.replay-preview-wrap {
  position: relative;
  width: 100%;
  max-width: 560px;
  align-self: center;
  aspect-ratio: 1200 / 630;
  border-radius: 8px;
  overflow: hidden;
  background: #18181a;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
  cursor: pointer;
}

.replay-preview {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.replay-preview-loaded { opacity: 1; }

.replay-preview-paused .replay-preview {
  filter: brightness(0.55);
}

.replay-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #fafafa;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  background: linear-gradient(180deg, rgba(10, 10, 10, 0.15), rgba(10, 10, 10, 0.4));
  pointer-events: none;
}

.replay-overlay-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(234, 88, 12, 0.92);
  color: #fff;
  font-size: 22px;
  box-shadow: 0 6px 18px rgba(234, 88, 12, 0.4);
}

.replay-empty {
  color: rgba(250, 250, 250, 0.55);
  font-size: 13px;
  text-align: center;
  padding: 28px 18px;
  line-height: 1.55;
  border: 1px dashed rgba(250, 250, 250, 0.18);
  border-radius: 8px;
}

.replay-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.replay-section .snippet-block {
  background: rgba(250, 250, 250, 0.04);
  border-color: rgba(250, 250, 250, 0.08);
}

.replay-section .snippet-head {
  background: rgba(250, 250, 250, 0.06);
  color: rgba(250, 250, 250, 0.7);
}

.replay-section .snippet-code {
  color: rgba(250, 250, 250, 0.85);
}

.replay-section .snippet-copy-btn {
  background: #ea580c;
}

.transcript-section {
  margin-top: 18px;
  padding: 14px 16px;
  background: #fafafa;
  border: 1px solid rgba(10, 10, 10, 0.08);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.transcript-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.transcript-icon {
  font-size: 18px;
  line-height: 1;
  padding-top: 2px;
}

.transcript-head-body {
  flex: 1;
  min-width: 0;
}

.transcript-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #0a0a0a;
  margin-bottom: 4px;
}

.transcript-sub {
  font-size: 12px;
  line-height: 1.5;
  color: #4a4a4a;
}

.transcript-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.transcript-download-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: #0a0a0a;
  color: #ffffff;
  text-decoration: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: background 0.15s;
}

.transcript-download-btn:hover { background: #2a2a2a; }

.transcript-download-btn-secondary {
  background: #fff;
  color: #0a0a0a;
  border: 1px solid rgba(10, 10, 10, 0.18);
}

.transcript-download-btn-secondary:hover {
  background: rgba(10, 10, 10, 0.04);
}

.transcript-empty {
  font-size: 12px;
  color: #6b6b6b;
  font-style: italic;
}

.transcript-snippet {
  margin: 0;
}

.outcome-section {
  margin-top: 18px;
  padding: 14px 16px;
  background: #fafafa;
  border: 1px dashed rgba(10, 10, 10, 0.18);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.outcome-section-live {
  background: rgba(255, 107, 26, 0.04);
  border-color: rgba(255, 107, 26, 0.3);
  border-style: solid;
}

.outcome-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.outcome-icon {
  font-size: 18px;
  line-height: 1;
  padding-top: 2px;
}

.outcome-head-body {
  flex: 1;
  min-width: 0;
}

.outcome-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #0a0a0a;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.outcome-saved-tag {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: none;
  color: var(--color-orange, #ff6b1a);
  background: rgba(255, 107, 26, 0.1);
  padding: 2px 8px;
  border-radius: 999px;
}

.outcome-sub {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #4a4a4a;
}

.outcome-sub a {
  color: var(--color-orange, #ff6b1a);
  text-decoration: none;
  font-weight: 600;
}

.outcome-sub a:hover { text-decoration: underline; }

.outcome-fields {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.outcome-fields-disabled { opacity: 0.55; }

.outcome-radio-group {
  display: flex;
  gap: 6px;
  border: none;
  margin: 0;
  padding: 0;
  flex-wrap: wrap;
}

.outcome-radio {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: 1px solid rgba(10, 10, 10, 0.16);
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  background: #fff;
  transition: border-color 0.15s, background 0.15s;
}

.outcome-radio input {
  appearance: none;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 1.5px solid rgba(10, 10, 10, 0.35);
  position: relative;
}

.outcome-radio input:checked {
  border-color: var(--color-orange, #ff6b1a);
  background: var(--color-orange, #ff6b1a);
  box-shadow: inset 0 0 0 2px #fff;
}

.outcome-radio-active {
  border-color: var(--color-orange, #ff6b1a);
  background: rgba(255, 107, 26, 0.08);
}

.outcome-radio-icon { font-family: sans-serif; }

.outcome-input,
.outcome-textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid rgba(10, 10, 10, 0.14);
  border-radius: 8px;
  font-size: 12.5px;
  font-family: inherit;
  background: #fff;
  color: #0a0a0a;
  resize: vertical;
}

.outcome-input:focus,
.outcome-textarea:focus {
  outline: none;
  border-color: var(--color-orange, #ff6b1a);
  box-shadow: 0 0 0 3px rgba(255, 107, 26, 0.12);
}

.outcome-input:disabled,
.outcome-textarea:disabled {
  background: rgba(10, 10, 10, 0.03);
  color: #6b6b6b;
  cursor: not-allowed;
}

.outcome-summary-counter {
  align-self: flex-end;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 10.5px;
  color: #6b6b6b;
  margin-top: -4px;
}

.outcome-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.outcome-submit {
  padding: 8px 16px;
  background: var(--color-orange, #ff6b1a);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  cursor: pointer;
  transition: background 0.15s;
}

.outcome-submit:hover:not(:disabled) {
  background: #0a0a0a;
}

.outcome-submit:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.outcome-link {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11.5px;
  color: var(--color-orange, #ff6b1a);
  text-decoration: none;
  font-weight: 600;
}

.outcome-link:hover { text-decoration: underline; }

.outcome-message {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.4;
  padding: 8px 10px;
  border-radius: 6px;
}

.outcome-message-success {
  background: rgba(67, 193, 101, 0.12);
  color: #1f6b35;
}

.outcome-message-error {
  background: rgba(255, 68, 68, 0.12);
  color: #b22020;
}

.gallery-callout {
  margin-top: 18px;
  padding: 14px 16px;
  background: #fafafa;
  border: 1px dashed rgba(10, 10, 10, 0.18);
  border-radius: 10px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.gallery-callout-live {
  background: rgba(255, 107, 26, 0.06);
  border-color: rgba(255, 107, 26, 0.45);
  border-style: solid;
}

.gallery-callout-icon {
  font-size: 22px;
  line-height: 1;
  color: var(--color-orange, #ff6b1a);
  padding-top: 2px;
}

.gallery-callout-body {
  flex: 1;
  min-width: 0;
}

.gallery-callout-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #0a0a0a;
  margin-bottom: 4px;
}

.gallery-callout-desc {
  font-size: 12.5px;
  line-height: 1.5;
  color: #4a4a4a;
}

.gallery-callout-desc a {
  color: var(--color-orange, #ff6b1a);
  text-decoration: none;
  font-weight: 600;
}

.gallery-callout-desc a:hover { text-decoration: underline; }

.gallery-callout-link {
  flex-shrink: 0;
  align-self: center;
  padding: 6px 12px;
  background: var(--color-orange, #ff6b1a);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  text-decoration: none;
  border-radius: 6px;
  white-space: nowrap;
  transition: background 0.15s ease;
}

.gallery-callout-link:hover {
  background: #0a0a0a;
}

.snippet-copy-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Transition */
.embed-dialog-enter-active,
.embed-dialog-leave-active {
  transition: opacity 0.2s ease;
}

.embed-dialog-enter-active .embed-dialog,
.embed-dialog-leave-active .embed-dialog {
  transition: transform 0.25s cubic-bezier(0.23, 1, 0.32, 1), opacity 0.25s ease;
}

.embed-dialog-enter-from,
.embed-dialog-leave-to { opacity: 0; }

.embed-dialog-enter-from .embed-dialog,
.embed-dialog-leave-to .embed-dialog {
  transform: translateY(8px) scale(0.98);
  opacity: 0;
}
</style>
