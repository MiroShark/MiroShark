<template>
  <div class="explore-container">
    <!-- Top Navigation Bar (mirrors Home.vue nav for visual consistency) -->
    <nav class="navbar">
      <router-link to="/" class="nav-brand" :title="$tr('Back to home', '返回首页')">MIROSHARK</router-link>
      <div class="nav-links">
        <router-link to="/" class="nav-link" :title="$tr('Back to home', '返回首页')">
          <span class="arrow">←</span> {{ $tr('Home', '首页') }}
        </router-link>
        <a
          href="https://github.com/aaronjmars/MiroShark"
          target="_blank"
          rel="noopener"
          class="github-link"
        >
          GitHub <span class="arrow">↗</span>
        </a>
        <LocaleToggle />
      </div>
    </nav>

    <div class="main-content">
      <!-- Header -->
      <header class="explore-header">
        <div class="tag-row">
          <span class="orange-tag">{{ verifiedOnly ? $tr('📍 Verified', '📍 已验证') : $tr('◎ Explore', '◎ 浏览') }}</span>
          <span class="meta-sep">·</span>
          <span class="meta-text">
            {{ verifiedOnly ? $tr('Predictions that called real events', '预言已对应真实事件') : $tr('Public simulation gallery', '公开模拟图库') }}
          </span>
        </div>
        <h1 class="page-title">{{ verifiedOnly ? $tr('Calls that landed.', '命中的预言。') : $tr('Simulations the community ran.', '社区运行的模拟。') }}</h1>
        <p class="page-subtitle">
          <template v-if="verifiedOnly">
            {{ $tr('Each card is a public MiroShark run whose operator marked the real-world outcome. Hover the badge for the source link, open one to see how the agent consensus formed, or fork it to test the same agent population on a fresh scenario.', '每张卡片都是一次由运营者标注了真实结果的公开 MiroShark 运行。将鼠标悬停在徽章上查看出处链接,点击查看智能体共识如何形成,或派生它以使用同一组智能体测试新的情景。') }}
          </template>
          <template v-else>
            {{ $tr("Every card is a real MiroShark run someone published. Open one to see the full belief drift, agent network, and prediction outcome — or fork it in one click and run your own variant with the same agent population.", '每张卡片都是有人发布的真实 MiroShark 运行。打开任一张可查看完整的信念漂移、智能体网络与预测结果 — 或一键派生,使用同一组智能体运行你自己的变体。') }}
          </template>
        </p>

        <!-- ── Search + filter bar ────────────────────────────────────
             Search and filter state lives in URL params (q, consensus,
             quality, sort) so a filtered view is bookmarkable and
             shareable — "every excellent-quality bearish call about
             Aave" becomes a URL you can tweet. -->
        <div class="filter-bar">
          <div class="search-wrap">
            <span class="search-icon">⌕</span>
            <input
              v-model="searchInput"
              type="search"
              class="search-input"
              :placeholder="$tr('Search scenarios…', '搜索情景…')"
              :aria-label="$tr('Search scenarios', '搜索情景')"
              autocomplete="off"
              @input="onSearchInput"
            />
            <button
              v-if="searchInput"
              type="button"
              class="search-clear"
              :title="$tr('Clear search', '清除搜索')"
              @click="clearSearch"
            >×</button>
          </div>

          <div class="chip-group" role="tablist" :aria-label="$tr('Consensus filter', '共识筛选')">
            <span class="chip-group-label">{{ $tr('Consensus', '共识') }}</span>
            <button
              v-for="opt in consensusOptions"
              :key="opt.value || 'any'"
              class="chip"
              :class="{ 'chip-active': consensus === opt.value }"
              :aria-pressed="consensus === opt.value"
              @click="setConsensus(opt.value)"
              :disabled="loading"
            >
              <span v-if="opt.glyph" class="chip-glyph" :class="opt.glyphClass">{{ opt.glyph }}</span>
              {{ opt.label() }}
            </button>
          </div>

          <div class="chip-group" role="tablist" :aria-label="$tr('Quality filter', '质量筛选')">
            <span class="chip-group-label">{{ $tr('Quality', '质量') }}</span>
            <button
              v-for="opt in qualityOptions"
              :key="opt.value || 'any'"
              class="chip"
              :class="{ 'chip-active': quality === opt.value }"
              :aria-pressed="quality === opt.value"
              @click="setQuality(opt.value)"
              :disabled="loading"
            >
              {{ opt.label() }}
            </button>
          </div>

          <div class="sort-wrap">
            <label class="sort-label" for="explore-sort">{{ $tr('Sort', '排序') }}</label>
            <select
              id="explore-sort"
              v-model="sortKey"
              class="sort-select"
              @change="onSortChange"
              :disabled="loading"
            >
              <option value="date">{{ $tr('Newest first', '最新优先') }}</option>
              <option value="rounds">{{ $tr('Most rounds', '轮次最多') }}</option>
              <option value="agents">{{ $tr('Most agents', '智能体最多') }}</option>
            </select>
          </div>

          <button
            v-if="filtersActive"
            type="button"
            class="reset-btn"
            @click="resetFilters"
            :disabled="loading"
            :title="$tr('Clear all filters', '清除所有筛选')"
          >
            ↻ {{ $tr('Reset', '重置') }}
          </button>
        </div>

        <p v-if="filtersActive && !loading" class="result-count">
          <template v-if="total === 0">
            {{ $tr('No simulations match the current filters.', '没有模拟符合当前筛选条件。') }}
          </template>
          <template v-else>
            {{ total }} {{ total === 1 ? $tr('result', '个结果') : $tr('results', '个结果') }}
          </template>
        </p>
        <div class="stats-row">
          <span class="stat-chip">
            <span class="stat-num">{{ loading ? '…' : total }}</span>
            <span class="stat-label">{{ verifiedOnly ? $tr('verified', '已验证') : $tr('published', '已发布') }}</span>
          </span>
          <span v-if="!verifiedOnly && !loading && items.length > 0" class="stat-chip">
            <span class="stat-num">{{ resolvedCount }}</span>
            <span class="stat-label">{{ $tr('resolved', '已结算') }}</span>
          </span>
          <span v-if="!verifiedOnly && !loading && items.length > 0" class="stat-chip">
            <span class="stat-num">{{ verifiedCount }}</span>
            <span class="stat-label">{{ $tr('verified', '已验证') }}</span>
          </span>

          <!-- Verified filter chip — toggles a `?verified=1` fetch + the
               /verified URL so the view is shareable. -->
          <button
            class="filter-chip"
            :class="{ 'filter-chip-active': verifiedFilter }"
            @click="toggleVerifiedFilter"
            :disabled="loading"
            :title="verifiedFilter ? $tr('Show all public simulations', '显示全部公开模拟') : $tr('Show only simulations with a recorded outcome', '只显示已记录结果的模拟')"
          >
            <span class="filter-chip-icon">📍</span>
            <span>{{ $tr('Verified only', '仅已验证') }}</span>
          </button>

          <!-- RSS subscription chip — feed mirrors the active view
               (verified-only when the filter is on). Drops the user into
               their RSS reader's "subscribe to feed" flow. -->
          <a
            class="filter-chip filter-chip-feed"
            :href="feedUrl"
            target="_blank"
            rel="noopener"
            :title="
              verifiedFilter
                ? $tr('Subscribe to verified-only Atom feed in Feedly / Readwise / Inoreader / NetNewsWire', '在 Feedly / Readwise / Inoreader / NetNewsWire 中订阅仅含已验证内容的 Atom 源')
                : $tr('Subscribe to all public simulations as an Atom feed in Feedly / Readwise / Inoreader / NetNewsWire', '在 Feedly / Readwise / Inoreader / NetNewsWire 中以 Atom 源订阅全部公开模拟')
            "
          >
            <span class="filter-chip-icon">📡</span>
            <span>{{ $tr('Subscribe via RSS', '通过 RSS 订阅') }}</span>
          </a>

          <button
            class="refresh-btn"
            @click="refresh"
            :disabled="loading"
            :title="$tr('Re-fetch the gallery', '重新获取图库')"
          >
            <span v-if="loading">…</span>
            <span v-else>{{ $tr('↻ Refresh', '↻ 刷新') }}</span>
          </button>
        </div>
      </header>

      <!-- Loading -->
      <div v-if="loading && items.length === 0" class="gallery-loading">
        <div class="loading-grid">
          <div v-for="n in 6" :key="n" class="loading-card"></div>
        </div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="gallery-error">
        <div class="error-icon">⚠</div>
        <div class="error-title">{{ $tr("Couldn't load the gallery", '无法加载图库') }}</div>
        <div class="error-msg">{{ error }}</div>
        <button class="error-retry" @click="refresh">{{ $tr('Try again', '重试') }}</button>
      </div>

      <!-- Empty -->
      <div v-else-if="items.length === 0" class="gallery-empty">
        <div class="empty-icon">{{ filtersActive ? '⌕' : (verifiedFilter ? '📍' : '◇') }}</div>
        <div class="empty-title">
          <template v-if="filtersActive">
            {{ $tr('No simulations match your filters.', '没有模拟符合你的筛选条件。') }}
          </template>
          <template v-else-if="verifiedFilter">
            {{ $tr('No verified predictions yet.', '暂无已验证的预言。') }}
          </template>
          <template v-else>
            {{ $tr('No public simulations yet.', '暂无公开模拟。') }}
          </template>
        </div>
        <div class="empty-msg">
          <template v-if="filtersActive">
            {{ $tr('Try widening the search — clear the keyword, switch the consensus chip back to All, or reset every filter at once.', '尝试放宽搜索 — 清空关键词、将共识切回「全部」,或一次性重置所有筛选。') }}
          </template>
          <template v-else-if="verifiedFilter">
            {{ $tr("Once an operator marks a public simulation's real-world outcome from the Embed dialog, it shows up here. In the meantime, browse every published run on", '当运营者从嵌入对话框中标记公开模拟的真实结果后,它会出现在这里。在此期间,可在以下位置浏览所有已发布的运行') }}
            <router-link to="/explore" class="inline-link">/explore</router-link>.
          </template>
          <template v-else>
            {{ $tr(`Yours could be first. Run a simulation, click the share icon on the result page, toggle "Public" — it'll appear here within 30 seconds.`, '你的可能是第一个。运行一次模拟,在结果页点击分享图标,切换为「公开」 — 它会在 30 秒内出现在这里。') }}
          </template>
        </div>
        <button
          v-if="filtersActive"
          type="button"
          class="empty-cta empty-cta-button"
          @click="resetFilters"
        >
          {{ $tr('Reset filters →', '重置筛选 →') }}
        </button>
        <router-link
          v-else
          :to="verifiedFilter ? '/explore' : '/'"
          class="empty-cta"
        >
          {{ verifiedFilter ? $tr('Browse all public sims →', '浏览全部公开模拟 →') : $tr('Run a simulation →', '运行一次模拟 →') }}
        </router-link>
      </div>

      <!-- Grid -->
      <div v-else class="gallery-grid">
        <article
          v-for="item in items"
          :key="item.simulation_id"
          class="gallery-card"
          :class="{
            'card-resolved': item.resolution_outcome,
            'card-verified-correct': item.outcome && item.outcome.label === 'correct',
            'card-verified-incorrect': item.outcome && item.outcome.label === 'incorrect',
            'card-verified-partial': item.outcome && item.outcome.label === 'partial',
          }"
        >
          <!-- Thumbnail: the server-rendered share card PNG -->
          <router-link
            :to="{ name: 'SimulationRun', params: { simulationId: item.simulation_id } }"
            class="card-thumb-link"
            :title="item.scenario || $tr('Open simulation', '打开模拟')"
          >
            <img
              :src="shareCardSrc(item)"
              class="card-thumb"
              alt=""
              loading="lazy"
              @error="onThumbError($event, item)"
            />
            <div class="card-thumb-overlay"></div>
          </router-link>

          <!-- Body -->
          <div class="card-body">
            <h2 class="card-scenario" :title="item.scenario">
              {{ item.scenario || $tr('(untitled scenario)', '(未命名情景)') }}
            </h2>

            <div class="card-pills">
              <component
                v-if="item.outcome && item.outcome.label"
                :is="item.outcome.outcome_url ? 'a' : 'span'"
                :href="item.outcome.outcome_url || undefined"
                :target="item.outcome.outcome_url ? '_blank' : undefined"
                :rel="item.outcome.outcome_url ? 'noopener noreferrer' : undefined"
                class="pill pill-verified"
                :class="outcomePillClass(item.outcome.label)"
                :title="outcomePillTitle(item.outcome)"
                @click.stop
              >
                {{ outcomePillIcon(item.outcome.label) }}
                {{ outcomePillLabel(item.outcome.label) }}
              </component>
              <span
                v-if="item.quality_health"
                class="pill"
                :class="qualityPillClass(item.quality_health)"
                :title="$tr('Quality health: ', '质量健康度:') + item.quality_health"
              >
                ◉ {{ item.quality_health }}
              </span>
              <span
                v-if="dominantStance(item)"
                class="pill"
                :class="stancePillClass(dominantStance(item).label)"
                :title="$tr('Final consensus: ', '最终共识:') + stanceTooltip(item)"
              >
                {{ stanceGlyph(dominantStance(item).label) }}
                {{ stanceLabel(dominantStance(item).label) }} {{ dominantStance(item).pct }}%
              </span>
              <span
                v-if="item.resolution_outcome"
                class="pill pill-resolved"
                :title="$tr('Real-world outcome recorded: ', '真实结果已记录:') + item.resolution_outcome"
              >
                ✓ {{ $tr('Resolved', '已结算') }} · {{ item.resolution_outcome }}
              </span>
              <span
                v-else
                class="pill pill-status"
                :title="$tr('Runner status: ', '运行状态:') + item.runner_status"
              >
                {{ formatStatus(item) }}
              </span>
            </div>

            <!-- Belief split bar -->
            <div v-if="item.final_consensus" class="consensus-bar" :title="stanceTooltip(item)">
              <div
                v-if="item.final_consensus.bullish > 0"
                class="bar-seg bar-bullish"
                :style="{ width: item.final_consensus.bullish + '%' }"
              ></div>
              <div
                v-if="item.final_consensus.neutral > 0"
                class="bar-seg bar-neutral"
                :style="{ width: item.final_consensus.neutral + '%' }"
              ></div>
              <div
                v-if="item.final_consensus.bearish > 0"
                class="bar-seg bar-bearish"
                :style="{ width: item.final_consensus.bearish + '%' }"
              ></div>
            </div>

            <div class="card-meta">
              <span class="meta-item">
                <span class="meta-label">{{ $tr('Agents', '智能体') }}</span>
                <span class="meta-val">{{ item.agent_count || 0 }}</span>
              </span>
              <span class="meta-sep">·</span>
              <span class="meta-item">
                <span class="meta-label">{{ $tr('Rounds', '轮次') }}</span>
                <span class="meta-val">
                  {{ item.current_round || 0 }}<span v-if="item.total_rounds">/{{ item.total_rounds }}</span>
                </span>
              </span>
              <span class="meta-sep">·</span>
              <span class="meta-item" :title="item.created_at">
                <span class="meta-val">{{ formatDate(item.created_at) }}</span>
              </span>
            </div>

            <!-- Actions -->
            <div class="card-actions">
              <router-link
                :to="{ name: 'SimulationRun', params: { simulationId: item.simulation_id } }"
                class="action-btn action-view"
              >
                {{ $tr('Open →', '打开 →') }}
              </router-link>
              <button
                class="action-btn action-fork"
                @click="forkAndOpen(item)"
                :disabled="forkingId === item.simulation_id"
                :title="$tr(`Copy this simulation's agents + config into a new run`, '将此模拟的智能体与配置复制到一次新的运行')"
              >
                <span v-if="forkingId === item.simulation_id">{{ $tr('Forking…', '派生中…') }}</span>
                <span v-else>{{ $tr('Fork this →', '派生此项 →') }}</span>
              </button>
            </div>
            <div
              v-if="forkErrors[item.simulation_id]"
              class="fork-error"
            >
              {{ forkErrors[item.simulation_id] }}
            </div>
          </div>
        </article>
      </div>

      <!-- Load more -->
      <div v-if="items.length > 0 && hasMore" class="load-more-row">
        <button
          class="load-more-btn"
          @click="loadMore"
          :disabled="loadingMore"
        >
          <span v-if="loadingMore">{{ $tr('Loading…', '加载中…') }}</span>
          <span v-else>{{ $tr('Load more', '加载更多') }} ({{ total - items.length }} {{ $tr('remaining', '剩余') }})</span>
        </button>
      </div>
    </div>

    <footer class="explore-footer">
      <span class="footer-line"></span>
      <span class="footer-text">
        {{ $tr(`Want yours here? Run a sim, open the Embed dialog, toggle "Public."`, '想让你的也出现在这里?运行一次模拟,打开嵌入对话框,切换为「公开」即可。') }}
      </span>
      <span class="footer-line"></span>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  getPublicSimulations,
  forkSimulation,
  getShareCardUrl,
  getFeedUrl,
} from '../api/simulation'
import LocaleToggle from '../components/LocaleToggle.vue'
import { tr } from '../i18n'

const props = defineProps({
  // When true, the view boots in verified-only mode. Wired to the
  // `/verified` route; users on `/explore` can also flip it on via the
  // filter chip in the header.
  verifiedOnly: { type: Boolean, default: false },
})

const router = useRouter()
const route = useRoute()

const items = ref([])
const total = ref(0)
const hasMore = ref(false)
const limit = 30
const loading = ref(false)
const loadingMore = ref(false)
const error = ref('')
const forkingId = ref('')
const forkErrors = ref({})
const verifiedFilter = ref(props.verifiedOnly)

// Filter state — initialised from the URL on mount so a deep link to
// `/explore?q=aave&consensus=bearish&quality=excellent&sort=rounds` boots
// directly into the filtered view. Backend normalises the values, so we
// just forward whatever's in the URL.
const ALLOWED_CONSENSUS = new Set(['bullish', 'neutral', 'bearish'])
const ALLOWED_QUALITY = new Set(['excellent', 'good', 'fair', 'poor'])
const ALLOWED_SORT = new Set(['date', 'rounds', 'agents'])

const _readEnumParam = (val, allowed) => {
  if (!val) return ''
  const s = String(val).trim().toLowerCase()
  return allowed.has(s) ? s : ''
}
const _readQueryParam = (val) => {
  if (val === undefined || val === null) return ''
  const s = String(val).trim()
  return s.length > 200 ? s.slice(0, 200) : s
}

const searchInput = ref(_readQueryParam(route.query.q))
const queryDebounced = ref(searchInput.value)
const consensus = ref(_readEnumParam(route.query.consensus, ALLOWED_CONSENSUS))
const quality = ref(_readEnumParam(route.query.quality, ALLOWED_QUALITY))
const sortKey = ref(_readEnumParam(route.query.sort, ALLOWED_SORT) || 'date')

const consensusOptions = [
  { value: '', label: () => tr('All', '全部') },
  { value: 'bullish', glyph: '▲', glyphClass: 'glyph-bullish', label: () => tr('Bullish', '看涨') },
  { value: 'neutral', glyph: '●', glyphClass: 'glyph-neutral', label: () => tr('Neutral', '中立') },
  { value: 'bearish', glyph: '▼', glyphClass: 'glyph-bearish', label: () => tr('Bearish', '看跌') },
]

const qualityOptions = [
  { value: '', label: () => tr('All', '全部') },
  { value: 'excellent', label: () => tr('Excellent', '优秀') },
  { value: 'good', label: () => tr('Good', '良好') },
  { value: 'fair', label: () => tr('Fair', '一般') },
  { value: 'poor', label: () => tr('Poor', '较差') },
]

const filtersActive = computed(
  () =>
    !!queryDebounced.value ||
    !!consensus.value ||
    !!quality.value ||
    sortKey.value !== 'date',
)

let _searchDebounceTimer = null
const onSearchInput = () => {
  // Debounce the network call so each keystroke doesn't paint the
  // gallery — but keep the input responsive to keep the typed value in
  // the URL the moment the user stops typing.
  if (_searchDebounceTimer) clearTimeout(_searchDebounceTimer)
  _searchDebounceTimer = setTimeout(() => {
    queryDebounced.value = searchInput.value.trim()
    syncQueryToRoute()
    refresh()
  }, 300)
}

const clearSearch = () => {
  searchInput.value = ''
  if (_searchDebounceTimer) clearTimeout(_searchDebounceTimer)
  queryDebounced.value = ''
  syncQueryToRoute()
  refresh()
}

const setConsensus = (value) => {
  if (consensus.value === value) return
  consensus.value = value
  syncQueryToRoute()
  refresh()
}

const setQuality = (value) => {
  if (quality.value === value) return
  quality.value = value
  syncQueryToRoute()
  refresh()
}

const onSortChange = () => {
  syncQueryToRoute()
  refresh()
}

const resetFilters = () => {
  searchInput.value = ''
  queryDebounced.value = ''
  consensus.value = ''
  quality.value = ''
  sortKey.value = 'date'
  if (_searchDebounceTimer) clearTimeout(_searchDebounceTimer)
  syncQueryToRoute()
  refresh()
}

// Mirror the active filter set to the URL so the page is shareable. We
// use `router.replace` (not `push`) so the back button doesn't pile up
// every keystroke.
const syncQueryToRoute = () => {
  const next = {}
  if (queryDebounced.value) next.q = queryDebounced.value
  if (consensus.value) next.consensus = consensus.value
  if (quality.value) next.quality = quality.value
  if (sortKey.value && sortKey.value !== 'date') next.sort = sortKey.value
  router.replace({ name: route.name, query: next }).catch(() => {})
}

const feedUrl = computed(() =>
  getFeedUrl({ format: 'atom', verified: verifiedFilter.value }),
)

const resolvedCount = computed(
  () => items.value.filter((item) => item.resolution_outcome).length,
)

const verifiedCount = computed(
  () => items.value.filter((item) => item.outcome && item.outcome.label).length,
)

const shareCardSrc = (item) => {
  // The backend includes a relative ``share_card_url``. Resolve against
  // the SPA origin so the <img> works whether the frontend is served by
  // Flask in production or by Vite in dev (the dev server proxies /api).
  if (item.share_card_url) {
    if (item.share_card_url.startsWith('http')) return item.share_card_url
    return item.share_card_url
  }
  return getShareCardUrl(item.simulation_id)
}

const onThumbError = (event, item) => {
  // Hide broken images (e.g. if the simulation was unpublished between
  // fetch and image load) — fall back to a monochrome tile so the card
  // still lays out evenly.
  const img = event?.target
  if (!img || img.dataset.fellBack === '1') return
  img.dataset.fellBack = '1'
  img.style.display = 'none'
}

const dominantStance = (item) => {
  const c = item.final_consensus
  if (!c) return null
  const entries = [
    { label: 'Bullish', pct: c.bullish ?? 0 },
    { label: 'Neutral', pct: c.neutral ?? 0 },
    { label: 'Bearish', pct: c.bearish ?? 0 },
  ]
  entries.sort((a, b) => b.pct - a.pct)
  const top = entries[0]
  if (!top || top.pct <= 0) return null
  return { label: top.label, pct: Math.round(top.pct) }
}

const stanceGlyph = (label) => {
  if (label === 'Bullish') return '▲'
  if (label === 'Bearish') return '▼'
  return '●'
}

const stancePillClass = (label) => {
  if (label === 'Bullish') return 'pill-bullish'
  if (label === 'Bearish') return 'pill-bearish'
  return 'pill-neutral'
}

const stanceLabel = (label) => {
  if (label === 'Bullish') return tr('Bullish', '看涨')
  if (label === 'Bearish') return tr('Bearish', '看跌')
  if (label === 'Neutral') return tr('Neutral', '中立')
  return label
}

const stanceTooltip = (item) => {
  const c = item.final_consensus
  if (!c) return ''
  const b = (c.bullish ?? 0).toFixed(1)
  const n = (c.neutral ?? 0).toFixed(1)
  const be = (c.bearish ?? 0).toFixed(1)
  return `${tr('Bullish', '看涨')} ${b}% · ${tr('Neutral', '中立')} ${n}% · ${tr('Bearish', '看跌')} ${be}%`
}

const qualityPillClass = (health) => {
  const h = String(health || '').toLowerCase()
  if (h.startsWith('excel')) return 'pill-quality-excellent'
  if (h.startsWith('good')) return 'pill-quality-good'
  if (h.startsWith('fair')) return 'pill-quality-fair'
  if (h.startsWith('poor')) return 'pill-quality-poor'
  return 'pill-quality-unknown'
}

const formatStatus = (item) => {
  const status = item.runner_status || item.status || 'idle'
  return String(status).replace(/_/g, ' ')
}

const formatDate = (iso) => {
  if (!iso) return '—'
  // Keep it cheap — just the YYYY-MM-DD prefix from the ISO string.
  return String(iso).slice(0, 10)
}

const outcomePillLabel = (label) => {
  if (label === 'correct') return tr('Verified', '已验证')
  if (label === 'incorrect') return tr('Called wrong', '预言落空')
  if (label === 'partial') return tr('Partial', '部分命中')
  return ''
}

const outcomePillIcon = (label) => {
  if (label === 'correct') return '📍'
  if (label === 'incorrect') return '⚠'
  if (label === 'partial') return '◑'
  return ''
}

const outcomePillClass = (label) => {
  if (label === 'correct') return 'pill-verified-correct'
  if (label === 'incorrect') return 'pill-verified-incorrect'
  if (label === 'partial') return 'pill-verified-partial'
  return ''
}

const outcomePillTitle = (outcome) => {
  if (!outcome) return ''
  const summary = (outcome.outcome_summary || '').trim()
  const link = outcome.outcome_url ? ` — ${outcome.outcome_url}` : ''
  if (summary) return summary + link
  return outcomePillLabel(outcome.label) + link
}

const loadPage = async (offset = 0) => {
  const res = await getPublicSimulations({
    limit,
    offset,
    verifiedOnly: verifiedFilter.value,
    q: queryDebounced.value || undefined,
    consensus: consensus.value || undefined,
    quality: quality.value || undefined,
    sort: sortKey.value || undefined,
  })
  if (!res?.success) {
    throw new Error(res?.error || tr('Request failed', '请求失败'))
  }
  return {
    data: res.data || [],
    total: Number.isFinite(res.total) ? res.total : (res.data?.length ?? 0),
    hasMore: !!res.has_more,
  }
}

const toggleVerifiedFilter = () => {
  verifiedFilter.value = !verifiedFilter.value
  // Keep the URL in lockstep with the filter so the page is shareable —
  // /verified for the curated hall, /explore for everything. Preserve
  // the active search/filter query string across the route swap so the
  // user doesn't lose their search when toggling Verified.
  const targetName = verifiedFilter.value ? 'Verified' : 'Explore'
  if (router.currentRoute.value.name !== targetName) {
    const carry = { ...route.query }
    router.replace({ name: targetName, query: carry }).catch(() => {})
  }
  refresh()
}

watch(
  () => props.verifiedOnly,
  (next) => {
    if (verifiedFilter.value !== next) {
      verifiedFilter.value = next
      refresh()
    }
  },
)

const refresh = async () => {
  loading.value = true
  error.value = ''
  try {
    const page = await loadPage(0)
    items.value = page.data
    total.value = page.total
    hasMore.value = page.hasMore
    forkErrors.value = {}
  } catch (err) {
    error.value =
      err?.response?.data?.error || err?.message || tr('Failed to load gallery', '无法加载图库')
  } finally {
    loading.value = false
  }
}

const loadMore = async () => {
  if (loadingMore.value || !hasMore.value) return
  loadingMore.value = true
  try {
    const page = await loadPage(items.value.length)
    const seen = new Set(items.value.map((item) => item.simulation_id))
    for (const incoming of page.data) {
      if (!seen.has(incoming.simulation_id)) items.value.push(incoming)
    }
    total.value = page.total
    hasMore.value = page.hasMore
  } catch (err) {
    error.value =
      err?.response?.data?.error || err?.message || tr('Failed to load more', '加载更多失败')
  } finally {
    loadingMore.value = false
  }
}

const forkAndOpen = async (item) => {
  if (forkingId.value) return
  forkingId.value = item.simulation_id
  forkErrors.value = { ...forkErrors.value, [item.simulation_id]: '' }
  try {
    const res = await forkSimulation({
      parent_simulation_id: item.simulation_id,
    })
    if (!res?.success) {
      throw new Error(res?.error || tr('Fork failed', '派生失败'))
    }
    const newId = res.data?.simulation_id
    if (!newId) throw new Error(tr('Fork did not return a simulation_id', '派生未返回 simulation_id'))
    router.push({ name: 'SimulationRun', params: { simulationId: newId } })
  } catch (err) {
    forkErrors.value = {
      ...forkErrors.value,
      [item.simulation_id]:
        err?.response?.data?.error || err?.message || tr('Fork failed', '派生失败'),
    }
  } finally {
    forkingId.value = ''
  }
}

onMounted(refresh)
</script>

<style scoped>
.explore-container {
  min-height: 100vh;
  background: var(--background);
  font-family: var(--font-display);
  color: var(--foreground);
}

/* ── Nav (matches Home.vue) ── */
.navbar {
  height: var(--space-xl);
  background: var(--color-black);
  color: var(--color-white);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 var(--space-lg);
}

.nav-brand {
  font-family: var(--font-mono);
  font-weight: 700;
  letter-spacing: 3px;
  font-size: 14px;
  text-transform: uppercase;
  color: var(--color-white);
  text-decoration: none;
  transition: var(--transition-fast);
}

.nav-brand:hover { color: var(--color-orange); }

.nav-links {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.nav-link,
.github-link {
  color: var(--color-white);
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 13px;
  letter-spacing: 1px;
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  transition: var(--transition-fast);
  opacity: 0.6;
}

.nav-link:hover,
.github-link:hover { opacity: 1; }

.arrow { font-family: sans-serif; }

/* ── Main Content ── */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: var(--space-2xl) var(--space-lg) var(--space-xl);
}

/* ── Header ── */
.explore-header {
  margin-bottom: var(--space-xl);
  max-width: 780px;
}

.tag-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-md);
  font-family: var(--font-mono);
  font-size: 13px;
}

.orange-tag {
  background: var(--color-orange);
  color: var(--color-white);
  padding: 4px var(--space-sm);
  letter-spacing: 1.5px;
  text-transform: uppercase;
  font-weight: 700;
}

.meta-sep { color: rgba(10, 10, 10, 0.35); }
.meta-text { color: rgba(10, 10, 10, 0.7); }

.page-title {
  font-family: var(--font-display);
  font-size: 52px;
  line-height: 1.1;
  margin-bottom: var(--space-md);
  letter-spacing: -0.5px;
}

.page-subtitle {
  font-size: 17px;
  line-height: 1.55;
  color: rgba(10, 10, 10, 0.7);
  margin-bottom: var(--space-lg);
}

.stats-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.stat-chip {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 6px 12px;
  background: var(--color-gray);
  border: var(--border-light);
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.5px;
}

.stat-num {
  font-weight: 700;
  font-size: 16px;
  color: var(--color-orange);
}

.stat-label {
  color: rgba(10, 10, 10, 0.5);
  text-transform: uppercase;
}

.refresh-btn {
  padding: 6px 12px;
  background: transparent;
  border: var(--border-medium);
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.5px;
  color: rgba(10, 10, 10, 0.7);
  cursor: pointer;
  transition: var(--transition-fast);
}

.refresh-btn:hover:not(:disabled) {
  color: var(--color-orange);
  border-color: var(--color-orange);
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── Loading skeleton ── */
.gallery-loading { margin-top: var(--space-lg); }

.loading-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-md);
}

.loading-card {
  height: 360px;
  background: linear-gradient(
    90deg,
    rgba(10, 10, 10, 0.04) 0%,
    rgba(10, 10, 10, 0.08) 50%,
    rgba(10, 10, 10, 0.04) 100%
  );
  background-size: 200% 100%;
  border: var(--border-light);
  animation: shimmer-bg 1.4s ease-in-out infinite;
}

@keyframes shimmer-bg {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ── Error ── */
.gallery-error,
.gallery-empty {
  padding: var(--space-2xl) var(--space-lg);
  border: var(--border-medium);
  text-align: center;
  max-width: 540px;
  margin: var(--space-xl) auto;
}

.error-icon,
.empty-icon {
  font-size: 32px;
  color: var(--color-orange);
  margin-bottom: var(--space-sm);
}

.error-title,
.empty-title {
  font-family: var(--font-display);
  font-size: 22px;
  margin-bottom: var(--space-sm);
}

.error-msg,
.empty-msg {
  color: rgba(10, 10, 10, 0.65);
  font-size: 15px;
  line-height: 1.5;
  margin-bottom: var(--space-md);
}

.error-retry,
.empty-cta {
  display: inline-block;
  padding: 10px 20px;
  background: var(--color-orange);
  color: var(--color-white);
  border: none;
  font-family: var(--font-mono);
  font-size: 13px;
  letter-spacing: 1px;
  text-transform: uppercase;
  text-decoration: none;
  cursor: pointer;
  transition: var(--transition-fast);
}

.error-retry:hover,
.empty-cta:hover {
  background: var(--color-black);
}

/* ── Grid ── */
.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-md);
  margin-top: var(--space-md);
}

.gallery-card {
  background: var(--color-white);
  border: var(--border-light);
  display: flex;
  flex-direction: column;
  transition: var(--transition-medium);
  animation: fade-in 0.4s ease-out;
}

.gallery-card:hover {
  border-color: var(--color-orange);
  transform: translateY(-2px);
}

.card-resolved {
  border-left: 3px solid var(--color-green);
}

/* ── Thumbnail ── */
.card-thumb-link {
  display: block;
  position: relative;
  aspect-ratio: 1200 / 630;
  background: var(--color-black);
  overflow: hidden;
}

.card-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: var(--transition-medium);
}

.gallery-card:hover .card-thumb {
  transform: scale(1.015);
}

.card-thumb-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    180deg,
    transparent 60%,
    rgba(10, 10, 10, 0.15) 100%
  );
  pointer-events: none;
}

/* ── Card body ── */
.card-body {
  padding: var(--space-md);
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  flex: 1;
}

.card-scenario {
  font-family: var(--font-display);
  font-size: 18px;
  line-height: 1.3;
  letter-spacing: -0.2px;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: calc(18px * 1.3 * 2);
}

.card-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 9px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  font-weight: 600;
  border-radius: 2px;
}

.pill-bullish {
  background: rgba(67, 193, 101, 0.15);
  color: #2a8545;
}

.pill-bearish {
  background: rgba(255, 68, 68, 0.14);
  color: #c52d2d;
}

.pill-neutral {
  background: rgba(10, 10, 10, 0.08);
  color: rgba(10, 10, 10, 0.7);
}

.pill-quality-excellent {
  background: rgba(67, 193, 101, 0.15);
  color: #2a8545;
}

.pill-quality-good {
  background: rgba(67, 193, 101, 0.1);
  color: #2a8545;
}

.pill-quality-fair {
  background: rgba(255, 179, 71, 0.18);
  color: #a66414;
}

.pill-quality-poor {
  background: rgba(255, 68, 68, 0.14);
  color: #c52d2d;
}

.pill-quality-unknown {
  background: rgba(10, 10, 10, 0.06);
  color: rgba(10, 10, 10, 0.5);
}

.pill-resolved {
  background: var(--color-green);
  color: var(--color-white);
}

.pill-status {
  background: rgba(10, 10, 10, 0.06);
  color: rgba(10, 10, 10, 0.55);
}

/* Verified-prediction pills — slightly stronger visual weight than the
   generic pills so the credibility signal lands at a glance. */
.pill-verified {
  text-decoration: none;
  cursor: default;
  letter-spacing: 0.6px;
}

a.pill-verified {
  cursor: pointer;
}

a.pill-verified:hover {
  filter: brightness(0.92);
}

.pill-verified-correct {
  background: var(--color-orange);
  color: var(--color-white);
}

.pill-verified-incorrect {
  background: rgba(255, 68, 68, 0.18);
  color: #c52d2d;
  outline: 1px solid rgba(255, 68, 68, 0.35);
  outline-offset: -1px;
}

.pill-verified-partial {
  background: rgba(255, 179, 71, 0.22);
  color: #8a4a0a;
  outline: 1px solid rgba(255, 179, 71, 0.5);
  outline-offset: -1px;
}

/* Card-level accent strip — same idea as .card-resolved (a thin coloured
   left border) but using the outcome palette so the verified hall reads
   at a glance even when scrolling fast. */
.card-verified-correct {
  border-left: 3px solid var(--color-orange);
}

.card-verified-incorrect {
  border-left: 3px solid var(--color-red);
}

.card-verified-partial {
  border-left: 3px solid #f59e0b;
}

/* Filter chip in the stats row — toggles `?verified=1`. Active state
   leans on the brand orange so it reads as the primary call-to-action
   when an operator is hunting for credibility-anchored sims. */
.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: transparent;
  border: var(--border-medium);
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.5px;
  color: rgba(10, 10, 10, 0.7);
  cursor: pointer;
  transition: var(--transition-fast);
  text-transform: uppercase;
}

.filter-chip:hover:not(:disabled) {
  border-color: var(--color-orange);
  color: var(--color-orange);
}

.filter-chip-active {
  background: var(--color-orange);
  border-color: var(--color-orange);
  color: var(--color-white);
}

.filter-chip-active:hover:not(:disabled) {
  background: var(--color-black);
  border-color: var(--color-black);
  color: var(--color-white);
}

.filter-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.filter-chip-icon {
  font-family: sans-serif;
}

/* The feed chip is visually subordinate to "Verified only" — it's a
   passive subscription action, not a content filter — so it reads as a
   muted text link until hover. */
.filter-chip-feed {
  text-decoration: none;
  color: rgba(10, 10, 10, 0.6);
  border-color: rgba(10, 10, 10, 0.18);
}

.filter-chip-feed:hover {
  border-color: var(--color-orange);
  color: var(--color-orange);
}

.inline-link {
  color: var(--color-orange);
  text-decoration: none;
  font-weight: 600;
}

.inline-link:hover {
  text-decoration: underline;
}

/* ── Consensus bar ── */
.consensus-bar {
  display: flex;
  height: 6px;
  background: rgba(10, 10, 10, 0.06);
  overflow: hidden;
  border-radius: 3px;
}

.bar-seg { height: 100%; transition: width 0.2s ease; }
.bar-bullish { background: var(--color-green); }
.bar-neutral { background: rgba(10, 10, 10, 0.3); }
.bar-bearish { background: var(--color-red); }

/* ── Metadata ── */
.card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10, 10, 10, 0.55);
  letter-spacing: 0.3px;
  flex-wrap: wrap;
}

.meta-item {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
}

.meta-label {
  text-transform: uppercase;
  color: rgba(10, 10, 10, 0.4);
}

.meta-val {
  color: rgba(10, 10, 10, 0.75);
  font-weight: 600;
}

/* ── Actions ── */
.card-actions {
  display: flex;
  gap: var(--space-xs);
  margin-top: auto;
  padding-top: var(--space-sm);
  border-top: 1px solid rgba(10, 10, 10, 0.06);
}

.action-btn {
  flex: 1;
  padding: 8px 12px;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 1px;
  text-transform: uppercase;
  text-decoration: none;
  text-align: center;
  border: var(--border-light);
  background: transparent;
  color: rgba(10, 10, 10, 0.75);
  cursor: pointer;
  transition: var(--transition-fast);
  font-weight: 600;
}

.action-view:hover {
  background: var(--color-black);
  color: var(--color-white);
  border-color: var(--color-black);
}

.action-fork {
  background: var(--color-orange);
  color: var(--color-white);
  border-color: var(--color-orange);
}

.action-fork:hover:not(:disabled) {
  background: var(--color-black);
  border-color: var(--color-black);
}

.action-fork:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.fork-error {
  margin-top: 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: #c52d2d;
  line-height: 1.4;
}

/* ── Load more ── */
.load-more-row {
  display: flex;
  justify-content: center;
  margin-top: var(--space-xl);
}

.load-more-btn {
  padding: 12px 32px;
  background: transparent;
  border: var(--border-medium);
  font-family: var(--font-mono);
  font-size: 13px;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: rgba(10, 10, 10, 0.75);
  cursor: pointer;
  transition: var(--transition-fast);
  font-weight: 600;
}

.load-more-btn:hover:not(:disabled) {
  background: var(--color-black);
  color: var(--color-white);
  border-color: var(--color-black);
}

.load-more-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── Footer ── */
.explore-footer {
  max-width: 1400px;
  margin: 0 auto;
  padding: var(--space-lg);
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  color: rgba(10, 10, 10, 0.4);
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.5px;
}

.footer-line {
  flex: 1;
  height: 1px;
  background: rgba(10, 10, 10, 0.08);
}

.footer-text { white-space: nowrap; }

/* ── Search + filter bar ── */
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-sm) var(--space-md);
  margin-top: var(--space-lg);
  padding: var(--space-md);
  background: var(--color-gray);
  border: var(--border-light);
}

.search-wrap {
  flex: 1 1 280px;
  position: relative;
  min-width: 240px;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 12px;
  font-family: var(--font-mono);
  font-size: 16px;
  color: rgba(10, 10, 10, 0.5);
  pointer-events: none;
}

.search-input {
  flex: 1;
  width: 100%;
  padding: 10px 36px 10px 36px;
  background: var(--color-white);
  border: var(--border-light);
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--foreground);
  letter-spacing: 0.3px;
  transition: var(--transition-fast);
  -webkit-appearance: none;
  appearance: none;
}

.search-input:focus {
  outline: none;
  border-color: var(--color-orange);
  background: var(--color-white);
}

.search-input::-webkit-search-decoration,
.search-input::-webkit-search-cancel-button {
  -webkit-appearance: none;
}

.search-clear {
  position: absolute;
  right: 8px;
  width: 22px;
  height: 22px;
  background: rgba(10, 10, 10, 0.08);
  border: none;
  border-radius: 50%;
  font-size: 14px;
  line-height: 1;
  color: rgba(10, 10, 10, 0.6);
  cursor: pointer;
  transition: var(--transition-fast);
}

.search-clear:hover {
  background: var(--color-orange);
  color: var(--color-white);
}

.chip-group {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.chip-group-label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  color: rgba(10, 10, 10, 0.45);
  margin-right: 4px;
  font-weight: 600;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 11px;
  background: var(--color-white);
  border: var(--border-light);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: rgba(10, 10, 10, 0.65);
  cursor: pointer;
  transition: var(--transition-fast);
  font-weight: 600;
}

.chip:hover:not(:disabled) {
  border-color: var(--color-orange);
  color: var(--color-orange);
}

.chip-active {
  background: var(--color-black);
  border-color: var(--color-black);
  color: var(--color-white);
}

.chip-active:hover:not(:disabled) {
  background: var(--color-orange);
  border-color: var(--color-orange);
  color: var(--color-white);
}

.chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chip-glyph {
  font-family: sans-serif;
  font-size: 10px;
  line-height: 1;
}

.glyph-bullish { color: #2a8545; }
.glyph-bearish { color: #c52d2d; }
.glyph-neutral { color: rgba(10, 10, 10, 0.55); }

.chip-active .chip-glyph {
  color: var(--color-white);
}

.sort-wrap {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.sort-label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  color: rgba(10, 10, 10, 0.45);
  font-weight: 600;
}

.sort-select {
  padding: 5px 24px 5px 10px;
  background: var(--color-white);
  border: var(--border-light);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.5px;
  color: rgba(10, 10, 10, 0.75);
  cursor: pointer;
  -webkit-appearance: none;
  appearance: none;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 10 10'><path d='M2 4l3 3 3-3' fill='none' stroke='rgba(10,10,10,0.5)' stroke-width='1.4' stroke-linecap='round' stroke-linejoin='round'/></svg>");
  background-repeat: no-repeat;
  background-position: right 8px center;
  font-weight: 600;
}

.sort-select:hover:not(:disabled) {
  border-color: var(--color-orange);
}

.sort-select:focus {
  outline: none;
  border-color: var(--color-orange);
}

.sort-select:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.reset-btn {
  padding: 5px 12px;
  background: transparent;
  border: 1px dashed rgba(10, 10, 10, 0.25);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: rgba(10, 10, 10, 0.6);
  cursor: pointer;
  transition: var(--transition-fast);
  font-weight: 600;
}

.reset-btn:hover:not(:disabled) {
  border-color: var(--color-orange);
  color: var(--color-orange);
  border-style: solid;
}

.reset-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.result-count {
  margin-top: var(--space-sm);
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.4px;
  color: rgba(10, 10, 10, 0.6);
}

.empty-cta-button {
  border: none;
  cursor: pointer;
}

/* ── Responsive ── */
@media (max-width: 720px) {
  .page-title { font-size: 36px; }
  .page-subtitle { font-size: 15px; }
  .main-content { padding: var(--space-xl) var(--space-md); }
  .gallery-grid { grid-template-columns: 1fr; }
  .filter-bar { padding: var(--space-sm); gap: var(--space-sm); }
  .search-wrap { flex: 1 1 100%; min-width: 0; }
  .chip-group { flex: 1 1 100%; }
  .sort-wrap { flex: 1 1 auto; }
}
</style>
