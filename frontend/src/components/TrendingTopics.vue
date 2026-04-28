<template>
  <div v-if="shouldRender" class="tt-wrap">
    <div class="tt-head">
      <span class="tt-label">
        <span class="tt-dot">◉</span> What's Trending
        <span class="tt-sub">{{ statusLine }}</span>
      </span>
      <button
        v-if="!loading"
        class="tt-refresh"
        type="button"
        title="Refresh feeds"
        @click="refresh"
      >↻</button>
    </div>

    <div v-if="loading && items.length === 0" class="tt-loading">
      <span class="tt-spinner"></span>
      Pulling current headlines from public feeds…
    </div>

    <div v-else-if="items.length > 0" class="tt-grid">
      <button
        v-for="(item, idx) in items"
        :key="item.url"
        type="button"
        class="tt-card"
        :disabled="busy"
        :title="item.title"
        @click="select(item, idx)"
      >
        <div class="tt-card-head">
          <span class="tt-source">{{ item.source_name }}</span>
          <span v-if="item.published_at" class="tt-time">
            {{ relativeTime(item.published_at) }}
          </span>
        </div>
        <div class="tt-title">{{ item.title }}</div>
        <div class="tt-cta">
          <span class="tt-cta-text">Simulate</span>
          <span class="tt-cta-arrow">→</span>
        </div>
      </button>
    </div>
  </div>
</template>

<script setup>
/**
 * TrendingTopics
 *
 * Renders the 5 most recent items from a configurable list of RSS/Atom feeds
 * (Reuters tech, The Verge, Hacker News, CoinDesk by default — operator can
 * override with TRENDING_FEEDS). Each card is a one-click jumping-off point:
 * the parent receives a `select` event with the URL and is expected to
 * push it into the same fetch + scenario-suggest pipeline that powers the
 * URL Import box.
 *
 * Designed to be silently absent when nothing is available — if every feed
 * errors, the API returns an empty `items` array and this component renders
 * nothing rather than a broken-looking placeholder.
 */

import { computed, onMounted, ref } from 'vue'
import { getTrendingTopics } from '../api/simulation'

const props = defineProps({
  // When true, the parent has an active fetch underway and we should
  // disable card clicks to avoid stacking concurrent URL fetches.
  busy: { type: Boolean, default: false },
})

const emit = defineEmits(['select'])

const items = ref([])
const loading = ref(false)
const fetchedAt = ref(null)
const cached = ref(false)
const errored = ref(false)

const shouldRender = computed(() => {
  if (loading.value) return true
  return items.value.length > 0
})

const statusLine = computed(() => {
  if (loading.value) return '// fetching…'
  if (!fetchedAt.value) return ''
  const ago = relativeTime(fetchedAt.value)
  return cached.value ? `// cached · refreshed ${ago}` : `// refreshed ${ago}`
})

const relativeTime = (iso) => {
  if (!iso) return ''
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return ''
  const diffSec = Math.max(0, Math.floor((Date.now() - t) / 1000))
  if (diffSec < 60) return 'just now'
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay}d ago`
}

const load = async ({ force = false } = {}) => {
  loading.value = true
  errored.value = false
  // Vite serves the page before Flask is fully warm — a single fetch
  // on mount often returns nothing, leaving the panel empty until the
  // user manually refreshes. Retry a few times on cold boot.
  const delays = force ? [0] : [0, 750, 1500, 3000]
  try {
    for (let i = 0; i < delays.length; i++) {
      if (delays[i]) await new Promise(r => setTimeout(r, delays[i]))
      try {
        const res = await getTrendingTopics({ refresh: force })
        if (res && res.success !== false) {
          const data = res.data || {}
          const list = Array.isArray(data.items) ? data.items : []
          if (list.length > 0 || i === delays.length - 1) {
            items.value = list
            fetchedAt.value = data.fetched_at || new Date().toISOString()
            cached.value = !!data.cached
            return
          }
        }
      } catch (_) {
        if (i === delays.length - 1) {
          items.value = []
          errored.value = true
        }
      }
    }
  } finally {
    loading.value = false
  }
}

const refresh = () => {
  if (loading.value) return
  load({ force: true })
}

const select = (item, idx) => {
  if (props.busy) return
  emit('select', { url: item.url, title: item.title, source: item.source_name, index: idx })
}

onMounted(() => {
  load()
})
</script>

<style scoped>
.tt-wrap {
  margin-top: var(--space-md);
  padding: var(--space-sm) var(--space-md);
  background: rgba(67, 193, 101, 0.04);
  border: 2px dashed rgba(67, 193, 101, 0.3);
  border-radius: 4px;
  font-family: var(--font-mono);
  position: relative;
}

.tt-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-sm);
}

.tt-label {
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--color-green);
  display: flex;
  align-items: center;
  gap: 8px;
}

.tt-dot {
  color: var(--color-green);
  font-size: 12px;
}

.tt-sub {
  color: rgba(10, 10, 10, 0.45);
  font-size: 10px;
  letter-spacing: 1px;
  font-weight: normal;
  text-transform: none;
}

.tt-refresh {
  background: none;
  border: 1px solid rgba(10, 10, 10, 0.15);
  color: rgba(10, 10, 10, 0.45);
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  padding: 3px 8px;
  border-radius: 2px;
  transition: var(--transition-fast);
}

.tt-refresh:hover {
  color: var(--color-green);
  border-color: var(--color-green);
}

.tt-loading {
  font-size: 11px;
  color: rgba(10, 10, 10, 0.55);
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 2px;
}

.tt-spinner {
  width: 10px;
  height: 10px;
  border: 2px solid rgba(67, 193, 101, 0.25);
  border-top-color: var(--color-green);
  border-radius: 50%;
  display: inline-block;
  animation: tt-spin 0.8s linear infinite;
}

@keyframes tt-spin {
  to { transform: rotate(360deg); }
}

.tt-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
}

.tt-card {
  background: var(--color-white);
  border: 2px solid rgba(10, 10, 10, 0.08);
  border-left: 4px solid var(--color-green);
  border-radius: 4px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: var(--transition-fast);
  min-height: 110px;
}

.tt-card:hover:not(:disabled) {
  border-color: var(--color-green);
  border-left-color: var(--color-green);
  transform: translateY(-1px);
}

.tt-card:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tt-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 9px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: rgba(10, 10, 10, 0.55);
}

.tt-source {
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 60%;
}

.tt-time {
  font-size: 9px;
  color: rgba(10, 10, 10, 0.4);
  letter-spacing: 0.5px;
  text-transform: none;
  flex-shrink: 0;
}

.tt-title {
  font-family: var(--font-display);
  font-size: 13px;
  color: var(--color-black);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}

.tt-cta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  margin-top: auto;
  font-size: 10px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--color-green);
}

.tt-cta-arrow {
  font-family: sans-serif;
  font-size: 13px;
}
</style>
