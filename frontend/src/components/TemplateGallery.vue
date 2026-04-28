<template>
  <div class="template-gallery">
    <div class="gallery-header">
      <div class="header-left">
        <span class="header-icon">◈</span>
        <span class="header-label">Quick Start Templates</span>
      </div>
      <span class="header-meta">{{ templates.length }} scenarios ready to launch</span>
    </div>

    <div v-if="loading" class="gallery-loading">
      Loading templates...
    </div>

    <div v-else-if="templates.length === 0" class="gallery-empty">
      No templates available.
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
          <span class="meta-item" :title="`~${template.estimated_agents} agents`">
            {{ template.estimated_agents }} agents
          </span>
          <span class="meta-dot">·</span>
          <span class="meta-item" :title="`~${template.estimated_rounds} rounds`">
            {{ template.estimated_rounds }} rounds
          </span>
          <span class="meta-dot">·</span>
          <span class="meta-item difficulty" :class="template.difficulty">
            {{ template.difficulty }}
          </span>
        </div>

        <div class="card-platforms">
          <span v-for="p in template.platforms" :key="p" class="platform-badge">{{ p }}</span>
          <span
            v-if="template.has_counterfactuals"
            class="platform-badge platform-badge--cf"
            :title="`${template.counterfactual_count} preset counterfactual branches`"
          >
            ⤷ {{ template.counterfactual_count }} branches
          </span>
          <span
            v-if="template.has_oracle_tools"
            class="platform-badge platform-badge--oracle"
            :title="`${template.oracle_tool_count} FeedOracle tools declared`"
          >
            ◎ live data
          </span>
        </div>

        <label
          v-if="template.has_oracle_tools"
          class="oracle-toggle"
          :class="{ disabled: !capabilities.oracle_seed_enabled }"
          :title="capabilities.oracle_seed_enabled
            ? 'Dispatch this template\'s oracle_tools against FeedOracle MCP before ingest.'
            : 'Oracle seeds disabled server-side. Set ORACLE_SEED_ENABLED=true in .env to enable.'"
          @click.stop
        >
          <input
            type="checkbox"
            :checked="oracleOptIn[template.id] || false"
            :disabled="!capabilities.oracle_seed_enabled"
            @change="toggleOracleOpt(template.id, $event.target.checked)"
          />
          <span>Use live oracle data</span>
        </label>

        <button
          class="launch-btn"
          :disabled="launchingId === template.id"
          @click.stop="launchTemplate(template)"
        >
          <span v-if="launchingId === template.id">Loading...</span>
          <span v-else-if="oracleOptIn[template.id] && capabilities.oracle_seed_enabled">Launch (live) →</span>
          <span v-else>Launch →</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listTemplates, getTemplate, getTemplateCapabilities } from '../api/templates'
import { setPendingTemplate } from '../store/pendingUpload'

const router = useRouter()

const templates = ref([])
const loading = ref(true)
const selectedId = ref(null)
const launchingId = ref(null)
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
.template-gallery {
  border: 1px solid #E5E5E5;
  padding: 30px;
  margin-top: 60px;
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
  gap: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: #999;
}

.header-icon {
  font-size: 1.2rem;
  color: #FF4500;
}

.header-meta {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #BBB;
}

.gallery-loading,
.gallery-empty {
  text-align: center;
  padding: 40px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  color: #999;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.template-card {
  border: 1px solid #E5E5E5;
  padding: 24px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  position: relative;
}

.template-card:hover {
  border-color: #999;
}

.template-card.selected {
  border-color: #FF4500;
  box-shadow: 0 0 0 1px #FF4500;
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
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.card-title {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0 0 8px 0;
  line-height: 1.3;
}

.card-desc {
  font-size: 0.85rem;
  color: #666;
  line-height: 1.6;
  margin: 0 0 16px 0;
  flex: 1;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: #999;
}

.meta-dot {
  color: #DDD;
}

.difficulty.easy { color: #22c55e; }
.difficulty.medium { color: #f59e0b; }
.difficulty.hard { color: #ef4444; }

.card-platforms {
  display: flex;
  gap: 6px;
  margin-bottom: 16px;
}

.platform-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  padding: 2px 8px;
  border: 1px solid #E5E5E5;
  color: #666;
  text-transform: lowercase;
  white-space: nowrap;
}

.card-platforms {
  flex-wrap: wrap;
  row-gap: 6px;
}

.platform-badge--cf {
  border-color: rgba(255, 107, 26, 0.3);
  color: #FF6B1A;
}

.platform-badge--oracle {
  border-color: rgba(67, 193, 101, 0.3);
  color: #2d8a3f;
}

.oracle-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: #2d8a3f;
  margin-bottom: 10px;
  cursor: pointer;
  user-select: none;
}

.oracle-toggle input[type="checkbox"] {
  accent-color: #2d8a3f;
  cursor: pointer;
}

.oracle-toggle.disabled {
  color: #aaa;
  cursor: not-allowed;
}

.oracle-toggle.disabled input[type="checkbox"] {
  cursor: not-allowed;
}

.launch-btn {
  width: 100%;
  padding: 10px;
  background: #000;
  color: #fff;
  border: none;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 0.5px;
}

.launch-btn:hover:not(:disabled) {
  background: #FF4500;
}

.launch-btn:disabled {
  background: #CCC;
  cursor: not-allowed;
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
