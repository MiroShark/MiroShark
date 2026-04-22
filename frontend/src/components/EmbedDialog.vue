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
import { ref, computed, watch } from 'vue'
import { publishSimulation, getEmbedSummary, getShareCardUrl, getShareLandingUrl } from '../api/simulation'

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

watch(() => props.open, async (val) => {
  if (!val) return
  copied.value = ''
  // Refresh public state when reopened — reflects external flips.
  try {
    const res = await getEmbedSummary(props.simulationId)
    if (typeof res?.data?.is_public === 'boolean') isPublic.value = res.data.is_public
  } catch (err) {
    if (err?.response?.status === 403) isPublic.value = false
  }
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
