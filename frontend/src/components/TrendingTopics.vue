<template>
  <div v-if="shouldRender" class="tt-wrap">
    <div class="tt-head">
      <span class="tt-label">
        <span class="tt-dot">◉</span> {{ $tr(`What's Trending`, '热门话题') }}
        <span class="tt-sub">{{ statusLine }}</span>
      </span>
      <button
        v-if="!loading"
        class="tt-refresh"
        type="button"
        :title="$tr('Refresh feeds', '刷新源')"
        @click="refresh"
      >↻</button>
    </div>

    <div v-if="loading && items.length === 0" class="tt-loading">
      <span class="tt-spinner"></span>
      {{ $tr('Pulling current headlines from public feeds…', '正在从公共源拉取最新头条…') }}
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
          <span class="tt-cta-text">{{ $tr('Simulate', '模拟') }}</span>
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
import { tr } from '../i18n'

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
  if (loading.value) return tr('// fetching…', '// 抓取中…')
  if (!fetchedAt.value) return ''
  const ago = relativeTime(fetchedAt.value)
  return cached.value ? `// ${tr('cached · refreshed', '已缓存 · 刷新于')} ${ago}` : `// ${tr('refreshed', '刷新于')} ${ago}`
})

const relativeTime = (iso) => {
  if (!iso) return ''
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return ''
  const diffSec = Math.max(0, Math.floor((Date.now() - t) / 1000))
  if (diffSec < 60) return tr('just now', '刚刚')
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}${tr('m ago', ' 分钟前')}`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}${tr('h ago', ' 小时前')}`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay}${tr('d ago', ' 天前')}`
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
/* Reskinned for the dark MiroShark Home — glossy violet panel,
   chrome accents, no orange/green Hyperstitions leftovers. */

.tt-wrap {
  margin-top: 1rem;
  padding: 0.95rem 1.1rem 1.05rem;
  border-radius: 1rem;
  background: linear-gradient(180deg, rgba(48, 36, 84, 0.45) 0%, rgba(20, 14, 42, 0.65) 100%);
  border: 1px solid rgba(167, 139, 250, 0.22);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.08),
    0 12px 28px -16px rgba(0, 0, 0, 0.7);
  font-family: 'Geist Mono', ui-monospace, 'SF Mono', Menlo, monospace;
  color: #f4f1ff;
  position: relative;
}

.tt-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.7rem;
  gap: 0.75rem;
}

.tt-label {
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: #c4b5fd;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.tt-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 9999px;
  background: radial-gradient(circle at 30% 30%, #ffffff 0%, #a78bfa 60%, #4c1d95 100%);
  box-shadow: 0 0 8px rgba(167, 139, 250, 0.9), 0 0 16px rgba(139, 92, 246, 0.6);
  /* Hides the original ◉ glyph; the CSS dot above replaces it. */
  font-size: 0;
  color: transparent;
}

.tt-sub {
  color: rgba(228, 222, 255, 0.55);
  font-size: 10px;
  letter-spacing: 0.04em;
  font-weight: normal;
  text-transform: none;
}

.tt-refresh {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 9999px;
  background: linear-gradient(180deg, rgba(70, 55, 120, 0.5) 0%, rgba(20, 14, 42, 0.75) 100%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(228, 222, 255, 0.7);
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
  transition: color 180ms ease, border-color 180ms ease, transform 180ms ease;
}

.tt-refresh:hover {
  color: #ffffff;
  border-color: rgba(167, 139, 250, 0.55);
  transform: translateY(-1px);
}

.tt-loading {
  font-size: 11px;
  color: rgba(228, 222, 255, 0.6);
  letter-spacing: 0.04em;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 2px;
}

.tt-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(167, 139, 250, 0.22);
  border-top-color: #c4b5fd;
  border-radius: 50%;
  display: inline-block;
  animation: tt-spin 0.8s linear infinite;
  box-shadow: 0 0 12px rgba(167, 139, 250, 0.4);
}

@keyframes tt-spin {
  to { transform: rotate(360deg); }
}

.tt-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.6rem;
}

.tt-card {
  position: relative;
  background: linear-gradient(180deg, rgba(40, 30, 70, 0.65) 0%, rgba(18, 12, 38, 0.85) 100%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 0.85rem;
  padding: 0.7rem 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  color: #f4f1ff;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.1),
    inset 0 -1px 0 rgba(0, 0, 0, 0.45);
  transition: border-color 180ms ease, transform 180ms ease, box-shadow 180ms ease;
  min-height: 110px;
  overflow: hidden;
}

/* Left accent rail — replaces the old 4px solid green border. */
.tt-card::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: linear-gradient(180deg, #a78bfa 0%, #c4b5fd 100%);
  box-shadow: 0 0 12px rgba(167, 139, 250, 0.6);
}

.tt-card:hover:not(:disabled) {
  border-color: rgba(167, 139, 250, 0.55);
  transform: translateY(-1px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.14),
    inset 0 -1px 0 rgba(0, 0, 0, 0.45),
    0 16px 36px -16px rgba(139, 92, 246, 0.5);
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
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: rgba(228, 222, 255, 0.6);
}

.tt-source {
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 60%;
  color: #c4b5fd;
}

.tt-time {
  font-size: 9px;
  color: rgba(228, 222, 255, 0.5);
  letter-spacing: 0.04em;
  text-transform: none;
  flex-shrink: 0;
}

.tt-title {
  font-family: 'Geist', system-ui, -apple-system, sans-serif;
  font-size: 13px;
  color: #f4f1ff;
  line-height: 1.4;
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
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #c4b5fd;
}

.tt-cta-arrow {
  font-family: sans-serif;
  font-size: 13px;
}
</style>
