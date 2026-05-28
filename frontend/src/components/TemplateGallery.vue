<template>
  <div class="template-gallery">
    <div class="gallery-header">
      <div class="header-left">
        <span class="header-icon">◈</span>
        <span class="header-label">{{ $tr('Quick Start Templates', '快速启动模板') }}</span>
      </div>
      <span class="header-meta">{{ templates.length }} {{ $tr('scenarios ready to launch', '个可用情景') }}</span>
    </div>

    <div v-if="loading" class="gallery-loading">
      {{ $tr('Loading templates...', '加载模板中...') }}
    </div>

    <div v-else-if="templates.length === 0" class="gallery-empty">
      {{ $tr('No templates available.', '暂无可用模板。') }}
    </div>

    <div v-else class="template-grid">
      <div
        v-for="template in templates"
        :key="template.id"
        class="template-card"
        :class="{ selected: selectedId === template.id, loading: launchingId === template.id }"
        @click="selectTemplate(template)"
      >
        <div class="card-top">
          <span class="card-icon">{{ iconMap[template.icon] || '◆' }}</span>
          <span class="card-category">{{ template.category }}</span>
        </div>

        <h3 class="card-title">{{ template.name }}</h3>
        <p class="card-desc">{{ template.description }}</p>

        <div class="card-meta">
          <span class="meta-item" :title="`~${template.estimated_agents} ` + $tr('agents', '个智能体')">
            {{ template.estimated_agents }} {{ $tr('agents', '智能体') }}
          </span>
          <span class="meta-dot">·</span>
          <span class="meta-item" :title="`~${template.estimated_rounds} ` + $tr('rounds', '轮次')">
            {{ template.estimated_rounds }} {{ $tr('rounds', '轮次') }}
          </span>
          <span class="meta-dot">·</span>
          <span class="meta-item difficulty" :class="template.difficulty">
            {{ template.difficulty === 'easy' ? $tr('easy', '简单') : template.difficulty === 'medium' ? $tr('medium', '中等') : template.difficulty === 'hard' ? $tr('hard', '困难') : template.difficulty }}
          </span>
        </div>

        <div class="card-platforms">
          <span v-for="p in template.platforms" :key="p" class="platform-badge">{{ p }}</span>
          <span
            v-if="template.has_counterfactuals"
            class="platform-badge platform-badge--cf"
            :title="`${template.counterfactual_count} ` + $tr('preset counterfactual branches', '个预设反事实分支')"
          >
            ⤷ {{ template.counterfactual_count }} {{ $tr('branches', '分支') }}
          </span>
          <span
            v-if="template.has_oracle_tools"
            class="platform-badge platform-badge--oracle"
            :title="`${template.oracle_tool_count} ` + $tr('FeedOracle tools declared', '个 FeedOracle 工具已声明')"
          >
            ◎ {{ $tr('live data', '实时数据') }}
          </span>
        </div>

        <label
          v-if="template.has_oracle_tools"
          class="oracle-toggle"
          :class="{ disabled: !capabilities.oracle_seed_enabled }"
          :title="capabilities.oracle_seed_enabled
            ? $tr(`Dispatch this template's oracle_tools against FeedOracle MCP before ingest.`, '在注入前调度此模板的 oracle_tools 对接 FeedOracle MCP。')
            : $tr('Oracle seeds disabled server-side. Set ORACLE_SEED_ENABLED=true in .env to enable.', '服务器已禁用 Oracle 种子。请在 .env 中设置 ORACLE_SEED_ENABLED=true 启用。')"
          @click.stop
        >
          <input
            type="checkbox"
            :checked="oracleOptIn[template.id] || false"
            :disabled="!capabilities.oracle_seed_enabled"
            @change="toggleOracleOpt(template.id, $event.target.checked)"
          />
          <span>{{ $tr('Use live oracle data', '使用实时 oracle 数据') }}</span>
        </label>

        <div class="card-actions">
          <button
            class="launch-btn"
            :disabled="launchingId === template.id"
            @click.stop="launchTemplate(template)"
          >
            <span v-if="launchingId === template.id">{{ $tr('Loading...', '加载中...') }}</span>
            <span v-else-if="oracleOptIn[template.id] && capabilities.oracle_seed_enabled">{{ $tr('Launch (live) →', '启动(实时)→') }}</span>
            <span v-else>{{ $tr('Launch →', '启动 →') }}</span>
          </button>
          <button
            class="copy-link-btn"
            :class="{ copied: copiedLinkId === template.id }"
            :title="$tr('Copy a shareable link that auto-launches this template', '复制可自动启动此模板的分享链接')"
            @click.stop="copyTemplateLink(template)"
          >
            <span v-if="copiedLinkId === template.id">✓</span>
            <span v-else>🔗</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listTemplates, getTemplate, getTemplateCapabilities } from '../api/templates'
import { setPendingTemplate } from '../store/pendingUpload'
import { buildTemplateShareUrl } from '../utils/urlParams'

const router = useRouter()

const templates = ref([])
const loading = ref(true)
const selectedId = ref(null)
const launchingId = ref(null)
const copiedLinkId = ref(null)
const capabilities = ref({ oracle_seed_enabled: false, mcp_agent_tools_enabled: false })
const oracleOptIn = reactive({})  // templateId → bool (opt-in per card)

const toggleOracleOpt = (templateId, checked) => {
  oracleOptIn[templateId] = checked
}

const iconMap = {
  vote: '🗳',
  chart: '📈',
  alert: '⚠',
  rocket: '🚀',
  clock: '⏳',
  school: '🎓'
}

// Retry the initial fetch a few times. The frontend (Vite) is up before
// the backend has finished warming up — a single attempt often returns
// nothing on first page load, leaving the gallery empty until the user
// refreshes. Backoff: 0ms, 750ms, 1500ms, 3000ms.
const fetchWithRetry = async () => {
  const delays = [0, 750, 1500, 3000]
  for (let i = 0; i < delays.length; i++) {
    if (delays[i]) await new Promise(r => setTimeout(r, delays[i]))
    try {
      const [listRes, capsRes] = await Promise.all([
        listTemplates(),
        getTemplateCapabilities().catch(() => null),
      ])
      if (capsRes?.success) capabilities.value = capsRes.data
      if (listRes?.success && Array.isArray(listRes.data) && listRes.data.length > 0) {
        templates.value = listRes.data
        return
      }
    } catch (e) {
      if (i === delays.length - 1) console.error('Failed to load templates:', e)
    }
  }
}

onMounted(async () => {
  try {
    await fetchWithRetry()
  } finally {
    loading.value = false
  }
})

const selectTemplate = (template) => {
  selectedId.value = selectedId.value === template.id ? null : template.id
}

const copyTemplateLink = async (template) => {
  if (!template?.id) return
  const url = buildTemplateShareUrl(template.id)
  try {
    await navigator.clipboard.writeText(url)
    copiedLinkId.value = template.id
    setTimeout(() => {
      if (copiedLinkId.value === template.id) copiedLinkId.value = null
    }, 1800)
  } catch (e) {
    console.warn('Copy failed:', e)
  }
}

const launchTemplate = async (template) => {
  launchingId.value = template.id
  try {
    const enrich = !!(oracleOptIn[template.id] && capabilities.value.oracle_seed_enabled)
    const res = await getTemplate(template.id, { enrich })
    if (res?.success) {
      const full = res.data
      setPendingTemplate(
        full.simulation_requirement,
        full.seed_document,
        full.name
      )
      router.push({ name: 'Process', params: { projectId: 'new' } })
    }
  } catch (e) {
    console.error('Failed to load template:', e)
  } finally {
    launchingId.value = null
  }
}
</script>

<style scoped>
/* MiroShark deep-space-violet — Template Gallery */
.template-gallery {
  border: 1px solid rgba(167,139,250,0.18);
  border-radius: 18px;
  padding: 30px;
  margin-top: 60px;
  background: linear-gradient(180deg, rgba(40,30,70,0.45) 0%, rgba(18,12,38,0.7) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.06),
    0 16px 36px -20px rgba(0,0,0,0.7);
  color: #f4f1ff;
  font-family: 'Geist', system-ui, -apple-system, sans-serif;
}

.gallery-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 25px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 11px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: rgba(196,181,253,0.85);
}

.header-icon {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 9999px;
  background: radial-gradient(circle at 30% 30%, #ffffff 0%, #a78bfa 60%, #4c1d95 100%);
  box-shadow: 0 0 10px rgba(167,139,250,0.8);
  font-size: 0;
  color: transparent;
}

.header-meta {
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 11px;
  letter-spacing: 0.06em;
  color: rgba(228,222,255,0.55);
}

.gallery-loading,
.gallery-empty {
  text-align: center;
  padding: 40px;
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 13px;
  color: rgba(228,222,255,0.55);
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
}

.template-card {
  position: relative;
  border: 1px solid rgba(255,255,255,0.06);
  background: linear-gradient(180deg, rgba(40,30,70,0.65) 0%, rgba(18,12,38,0.85) 100%);
  border-radius: 14px;
  padding: 22px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  color: #f4f1ff;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.08),
    inset 0 -1px 0 rgba(0,0,0,0.4);
  transition: border-color 180ms ease, transform 180ms ease, box-shadow 180ms ease;
}

.template-card::before {
  content: '';
  position: absolute;
  top: 18px;
  left: 0;
  width: 2px;
  height: 28px;
  border-radius: 0 2px 2px 0;
  background: linear-gradient(180deg, #a78bfa 0%, #c4b5fd 100%);
  box-shadow: 0 0 10px rgba(167,139,250,0.6);
}

.template-card:hover {
  border-color: rgba(167,139,250,0.55);
  transform: translateY(-1px);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.12),
    0 16px 36px -16px rgba(139,92,246,0.5);
}

.template-card.selected {
  border-color: rgba(167,139,250,0.7);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.15),
    0 0 0 1px rgba(167,139,250,0.5),
    0 16px 36px -16px rgba(139,92,246,0.7);
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.card-icon {
  font-size: 1.4rem;
}

.card-category {
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 10px;
  color: rgba(196,181,253,0.7);
  text-transform: uppercase;
  letter-spacing: 0.18em;
}

.card-title {
  font-family: 'Geist', system-ui, sans-serif;
  font-size: 1.05rem;
  font-weight: 600;
  margin: 0 0 8px 0;
  line-height: 1.3;
  color: #ffffff;
}

.card-desc {
  font-size: 0.85rem;
  color: rgba(228,222,255,0.7);
  line-height: 1.6;
  margin: 0 0 16px 0;
  flex: 1;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 11px;
  color: rgba(228,222,255,0.55);
}

.meta-dot {
  color: rgba(196,181,253,0.4);
}

.difficulty.easy { color: #c4b5fd; }
.difficulty.medium { color: #fcd34d; }
.difficulty.hard { color: #f0abfc; }

.card-platforms {
  display: flex;
  gap: 6px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  row-gap: 6px;
}

.platform-badge {
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 10px;
  padding: 3px 10px;
  border: 1px solid rgba(255,255,255,0.08);
  background: linear-gradient(180deg, rgba(40,30,70,0.55) 0%, rgba(18,12,38,0.7) 100%);
  border-radius: 9999px;
  color: rgba(228,222,255,0.8);
  text-transform: lowercase;
  white-space: nowrap;
}

.platform-badge--cf {
  border-color: rgba(167,139,250,0.35);
  color: #c4b5fd;
}

.platform-badge--oracle {
  border-color: rgba(196,181,253,0.35);
  color: #c4b5fd;
}

.oracle-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 11px;
  color: rgba(196,181,253,0.85);
  margin-bottom: 10px;
  cursor: pointer;
  user-select: none;
}

.oracle-toggle input[type="checkbox"] {
  accent-color: #a78bfa;
  cursor: pointer;
}

.oracle-toggle.disabled {
  color: rgba(228,222,255,0.35);
  cursor: not-allowed;
}

.oracle-toggle.disabled input[type="checkbox"] {
  cursor: not-allowed;
}

.card-actions {
  display: flex;
  align-items: stretch;
  gap: 8px;
}

.launch-btn {
  flex: 1;
  padding: 11px;
  background: linear-gradient(180deg, rgba(167,139,250,0.55) 0%, rgba(76,29,149,0.75) 100%);
  color: #ffffff;
  border: 1px solid rgba(167,139,250,0.55);
  border-radius: 9999px;
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.2),
    0 8px 22px -10px rgba(139,92,246,0.7);
  transition: transform 180ms ease, box-shadow 180ms ease;
}

.launch-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.25),
    0 12px 28px -10px rgba(139,92,246,0.85);
}

.launch-btn:disabled {
  background: linear-gradient(180deg, rgba(40,30,70,0.4) 0%, rgba(18,12,38,0.6) 100%);
  color: rgba(228,222,255,0.35);
  border-color: rgba(255,255,255,0.06);
  cursor: not-allowed;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
}

.copy-link-btn {
  flex-shrink: 0;
  width: 42px;
  background: linear-gradient(180deg, rgba(40,30,70,0.55) 0%, rgba(18,12,38,0.85) 100%);
  color: rgba(228,222,255,0.7);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 9999px;
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
  transition: color 180ms ease, border-color 180ms ease, transform 180ms ease;
}

.copy-link-btn:hover {
  color: #ffffff;
  border-color: rgba(167,139,250,0.55);
  transform: translateY(-1px);
}

.copy-link-btn.copied {
  color: #c4b5fd;
  border-color: rgba(196,181,253,0.55);
}

@media (max-width: 1024px) {
  .template-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .template-grid {
    grid-template-columns: 1fr;
  }
}
</style>
