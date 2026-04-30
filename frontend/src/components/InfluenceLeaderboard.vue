<template>
  <div class="influence-leaderboard">
    <!-- Header -->
    <div class="lb-header">
      <div class="lb-title">
        <span class="lb-icon">◈</span>
        <span class="lb-label">{{ $tr('AGENT INFLUENCE LEADERBOARD', '智能体影响力排行榜') }}</span>
      </div>
      <button
        class="export-btn"
        :disabled="!agents.length"
        @click="exportReport"
        :title="$tr('Download influence report as JSON', '下载影响力报告 JSON')"
      >
        {{ $tr('Export JSON ↓', '导出 JSON ↓') }}
      </button>
    </div>

    <!-- Interview Modal -->
    <teleport to="body">
      <div v-if="interviewAgent" class="iv-overlay" @click.self="closeInterview">
        <div class="iv-modal">
          <!-- Modal Header -->
          <div class="iv-header">
            <div class="iv-agent-info">
              <div class="iv-avatar">{{ interviewAgent.agent_name[0].toUpperCase() }}</div>
              <div>
                <div class="iv-name">{{ interviewAgent.agent_name }}</div>
                <div class="iv-meta">
                  {{ $tr('Rank', '排名') }} #{{ interviewAgent.rank }} · {{ interviewAgent.influence_score }} {{ $tr('pts', '分') }}
                  · {{ interviewAgent.posts_created }} {{ $tr('posts', '帖子') }}
                </div>
              </div>
            </div>
            <button class="iv-close" @click="closeInterview">✕</button>
          </div>

          <!-- Chat thread -->
          <div class="iv-thread" ref="threadEl">
            <div v-if="!interviewHistory.length && !interviewLoading" class="iv-empty">
              {{ $tr('Ask', '询问') }} {{ interviewAgent.agent_name }} {{ $tr('about their simulation experience.', '关于他们的模拟体验。') }}
              {{ $tr(`Try: "Why did you post so much in the early rounds?" or "What changed your mind?"`, '试试:"你为什么在前几轮发帖这么多?" 或 "什么改变了你的想法?"') }}
            </div>
            <div
              v-for="(qa, i) in interviewHistory"
              :key="i"
              class="iv-qa-pair"
            >
              <div class="iv-question">
                <span class="iv-role">{{ $tr('You', '你') }}</span>
                <span class="iv-text">{{ qa.question }}</span>
              </div>
              <div class="iv-answer">
                <span class="iv-role agent">{{ interviewAgent.agent_name }}</span>
                <span class="iv-text">{{ qa.answer }}</span>
              </div>
            </div>
            <div v-if="interviewLoading" class="iv-thinking">
              <div class="iv-dots"><span></span><span></span><span></span></div>
              <span>{{ interviewAgent.agent_name }} {{ $tr('is thinking...', '正在思考...') }}</span>
            </div>
          </div>

          <!-- Input -->
          <div class="iv-input-row">
            <input
              ref="questionInput"
              v-model="interviewQuestion"
              class="iv-input"
              type="text"
              :placeholder="$tr('Ask a question...', '提问...')"
              :disabled="interviewLoading"
              @keydown.enter.prevent="submitQuestion"
            />
            <button
              class="iv-send"
              :disabled="interviewLoading || !interviewQuestion.trim()"
              @click="submitQuestion"
            >
              {{ $tr('Ask', '提问') }}
            </button>
          </div>

          <!-- Error -->
          <div v-if="interviewError" class="iv-error">{{ interviewError }}</div>
        </div>
      </div>
    </teleport>

    <!-- Score legend -->
    <div class="lb-legend">
      <span class="legend-item"><span class="legend-dot engage"></span>{{ $tr('Engagement ×3', '互动 ×3') }}</span>
      <span class="legend-item"><span class="legend-dot platform"></span>{{ $tr('Platforms ×5', '平台 ×5') }}</span>
      <span class="legend-item"><span class="legend-dot post"></span>{{ $tr('Posts ×1', '帖子 ×1') }}</span>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="lb-loading">
      <div class="pulse-ring"></div>
      <span>{{ $tr('Computing influence scores...', '正在计算影响力分数...') }}</span>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="lb-error">{{ error }}</div>

    <!-- Empty -->
    <div v-else-if="!agents.length" class="lb-empty">
      {{ $tr('No simulation data available yet. Run the simulation first.', '尚无模拟数据。请先运行模拟。') }}
    </div>

    <!-- Leaderboard rows -->
    <div v-else class="lb-list">
      <div
        v-for="agent in agents"
        :key="agent.agent_name"
        class="lb-row"
        :class="{ 'top-three': agent.rank <= 3 }"
      >
        <!-- Rank -->
        <div class="lb-rank" :class="'rank-' + Math.min(agent.rank, 4)">
          {{ String(agent.rank).padStart(2, '0') }}
        </div>

        <!-- Agent identity -->
        <div class="lb-identity">
          <div class="lb-avatar">{{ agent.agent_name[0].toUpperCase() }}</div>
          <div class="lb-info">
            <div class="lb-name">{{ agent.agent_name }}</div>
            <div class="lb-platforms">
              <span v-if="agent.platforms.includes('twitter')" class="platform-pill twitter">X</span>
              <span v-if="agent.platforms.includes('reddit')" class="platform-pill reddit">Reddit</span>
              <span v-if="agent.platforms.includes('polymarket')" class="platform-pill polymarket">PM</span>
            </div>
          </div>
        </div>

        <!-- Score breakdown -->
        <div class="lb-breakdown">
          <div class="bd-item" :title="$tr('Engagement received (likes, reposts, quotes)', '收到的互动(点赞、转发、引用)')">
            <span class="bd-label engage">{{ $tr('ENG', '互动') }}</span>
            <span class="bd-value">{{ agent.engagement_received }}</span>
          </div>
          <div class="bd-item" :title="$tr('Original posts created', '发布的原创帖子')">
            <span class="bd-label post">{{ $tr('PST', '帖子') }}</span>
            <span class="bd-value">{{ agent.posts_created }}</span>
          </div>
        </div>

        <!-- Score bar + value -->
        <div class="lb-score">
          <span class="score-num">{{ agent.influence_score }}</span>
          <div class="score-bar-track">
            <div
              class="score-bar-fill"
              :style="{ width: scoreBarPct(agent.influence_score) + '%' }"
            ></div>
          </div>
        </div>

        <!-- Interview button -->
        <button
          class="iv-btn"
          @click.stop="openInterview(agent)"
          :title="$tr('Interview this agent about their simulation', '采访这位智能体关于其模拟的经历')"
        >
          ▶ {{ $tr('Interview', '采访') }}
        </button>
      </div>
    </div>

    <!-- Footer -->
    <div v-if="totalAgents > agents.length" class="lb-footer">
      {{ $tr('Showing top', '显示前') }} {{ agents.length }} {{ $tr('of', '/共') }} {{ totalAgents }} {{ $tr('agents', '个智能体') }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { getInfluenceLeaderboard, traceInterviewAgent, getAgentInterview } from '../api/simulation'
import { tr } from '../i18n'

const props = defineProps({
  simulationId: { type: String, required: true },
  visible: { type: Boolean, default: false }
})

const loading = ref(false)
const error = ref('')
const agents = ref([])
const totalAgents = ref(0)

// Interview state
const interviewAgent = ref(null)
const interviewHistory = ref([])
const interviewQuestion = ref('')
const interviewLoading = ref(false)
const interviewError = ref('')
const threadEl = ref(null)
const questionInput = ref(null)

const maxScore = computed(() =>
  agents.value.length ? agents.value[0].influence_score : 1
)

const scoreBarPct = (score) => {
  const max = maxScore.value || 1
  return Math.round((score / max) * 100)
}

const load = async () => {
  if (!props.simulationId) return
  loading.value = true
  error.value = ''
  try {
    const res = await getInfluenceLeaderboard(props.simulationId)
    if (res.success && res.data) {
      agents.value = res.data.agents || []
      totalAgents.value = res.data.total_agents || 0
    } else {
      error.value = res.error || tr('Failed to load influence data.', '加载影响力数据失败。')
    }
  } catch (err) {
    error.value = err.message || tr('Failed to load influence data.', '加载影响力数据失败。')
  } finally {
    loading.value = false
  }
}

const exportReport = () => {
  const payload = {
    simulation_id: props.simulationId,
    generated_at: new Date().toISOString(),
    agents: agents.value,
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `influence-report-${props.simulationId}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// ── Interview ──

const openInterview = async (agent) => {
  interviewAgent.value = agent
  interviewHistory.value = []
  interviewQuestion.value = ''
  interviewError.value = ''

  // Load existing transcript
  try {
    const res = await getAgentInterview(props.simulationId, agent.agent_name)
    if (res.data?.success && res.data.data.qa_pairs?.length) {
      interviewHistory.value = res.data.data.qa_pairs
    }
  } catch (_) {
    // No transcript yet — that's fine
  }

  await nextTick()
  questionInput.value?.focus()
  scrollThread()
}

const closeInterview = () => {
  interviewAgent.value = null
  interviewHistory.value = []
  interviewQuestion.value = ''
  interviewError.value = ''
}

const submitQuestion = async () => {
  const question = interviewQuestion.value.trim()
  if (!question || interviewLoading.value) return

  interviewLoading.value = true
  interviewError.value = ''
  interviewQuestion.value = ''

  try {
    // Build history for multi-turn context (last 6 exchanges to keep tokens bounded)
    const history = interviewHistory.value.slice(-6).flatMap(qa => [
      { role: 'user', content: qa.question },
      { role: 'assistant', content: qa.answer },
    ])

    const res = await traceInterviewAgent(props.simulationId, interviewAgent.value.agent_name, {
      question,
      history,
    })

    if (res.success) {
      interviewHistory.value.push({
        question,
        answer: res.data.answer,
        timestamp: new Date().toISOString(),
      })
      await nextTick()
      scrollThread()
    } else {
      interviewError.value = res.error || tr('Failed to get a response.', '未能获取回复。')
    }
  } catch (err) {
    interviewError.value = err.message || tr('Request failed.', '请求失败。')
  } finally {
    interviewLoading.value = false
    await nextTick()
    questionInput.value?.focus()
  }
}

const scrollThread = () => {
  if (threadEl.value) {
    threadEl.value.scrollTop = threadEl.value.scrollHeight
  }
}

const shareQA = (qa) => {
  const name = interviewAgent.value?.agent_name || 'Agent'
  const text = `I interviewed ${name} (AI simulation agent)\n\nQ: ${qa.question}\n\nA: ${qa.answer}`
  const card = text.length > 280 ? text.slice(0, 277) + '...' : text
  navigator.clipboard.writeText(card).catch(() => {})
}

// Load when becoming visible or when simulationId changes
watch(() => props.visible, (val) => { if (val) load() })
watch(() => props.simulationId, () => { if (props.visible) load() })
onMounted(() => { if (props.visible) load() })
</script>

<style scoped>
/* ── Container ── */
.influence-leaderboard {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  font-family: var(--font-mono);
  background: var(--background);
}

/* ── Header ── */
.lb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.08);
  flex-shrink: 0;
}

.lb-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.lb-icon {
  color: var(--color-green);
  font-size: 14px;
}

.lb-label {
  font-size: 12px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.5);
}

.export-btn {
  background: none;
  border: 1px solid rgba(10,10,10,0.15);
  padding: 4px 10px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 1px;
  cursor: pointer;
  color: rgba(10,10,10,0.5);
  transition: all 0.15s ease;
}

.export-btn:hover:not(:disabled) {
  border-color: var(--color-orange);
  color: var(--color-orange);
}

.export-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* ── Legend ── */
.lb-legend {
  display: flex;
  gap: 16px;
  padding: 8px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.05);
  flex-shrink: 0;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: rgba(10,10,10,0.35);
  letter-spacing: 1px;
}

.legend-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.legend-dot.engage { background: var(--color-orange); }
.legend-dot.follow { background: var(--color-green); }
.legend-dot.platform { background: #8b5cf6; }
.legend-dot.post { background: rgba(10,10,10,0.3); }

/* ── States ── */
.lb-loading,
.lb-empty,
.lb-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 12px;
  padding: 40px;
  font-size: 13px;
  color: rgba(10,10,10,0.35);
  letter-spacing: 1px;
}

.lb-error { color: var(--color-red, #e53e3e); }

.pulse-ring {
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-orange);
  border-radius: 50%;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.4); opacity: 0.4; }
}

/* ── List ── */
.lb-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.lb-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.04);
  transition: background 0.1s ease;
}

.lb-row:hover {
  background: rgba(10,10,10,0.02);
}

.lb-row.top-three {
  border-left: 3px solid var(--color-orange);
}

/* ── Rank ── */
.lb-rank {
  width: 28px;
  font-size: 13px;
  font-weight: 700;
  color: rgba(10,10,10,0.2);
  flex-shrink: 0;
  text-align: right;
}

.lb-rank.rank-1 { color: #f59e0b; }
.lb-rank.rank-2 { color: rgba(10,10,10,0.5); }
.lb-rank.rank-3 { color: #b45309; }

/* ── Identity ── */
.lb-identity {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.lb-avatar {
  width: 28px;
  height: 28px;
  background: rgba(10,10,10,0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: rgba(10,10,10,0.4);
  flex-shrink: 0;
}

.lb-info {
  min-width: 0;
}

.lb-name {
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--foreground);
  margin-bottom: 3px;
}

.lb-platforms {
  display: flex;
  gap: 4px;
}

.platform-pill {
  font-size: 9px;
  padding: 1px 5px;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.platform-pill.twitter { background: rgba(10,10,10,0.07); color: rgba(10,10,10,0.5); }
.platform-pill.reddit { background: rgba(255,69,0,0.1); color: #c44b00; }
.platform-pill.polymarket { background: rgba(99,102,241,0.1); color: #4f46e5; }

/* ── Breakdown ── */
.lb-breakdown {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.bd-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  min-width: 32px;
}

.bd-label {
  font-size: 9px;
  letter-spacing: 1px;
  opacity: 0.5;
}

.bd-label.engage { color: var(--color-orange); }
.bd-label.follow { color: var(--color-green); }
.bd-label.post   { color: rgba(10,10,10,0.5); }

.bd-value {
  font-size: 13px;
  font-weight: 700;
  color: var(--foreground);
}

/* ── Score ── */
.lb-score {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
  min-width: 60px;
}

.score-num {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-orange);
}

.score-bar-track {
  width: 60px;
  height: 3px;
  background: rgba(10,10,10,0.08);
}

.score-bar-fill {
  height: 100%;
  background: var(--color-orange);
  transition: width 0.4s ease;
}

/* ── Footer ── */
.lb-footer {
  padding: 8px 16px;
  font-size: 11px;
  color: rgba(10,10,10,0.3);
  letter-spacing: 1px;
  text-align: center;
  border-top: 1px solid rgba(10,10,10,0.05);
  flex-shrink: 0;
}

/* ── Interview button ── */
.iv-btn {
  flex-shrink: 0;
  background: none;
  border: 1px solid rgba(10,10,10,0.15);
  padding: 3px 8px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 1px;
  cursor: pointer;
  color: rgba(10,10,10,0.45);
  transition: all 0.15s ease;
  white-space: nowrap;
}

.iv-btn:hover {
  border-color: var(--color-green, #43C165);
  color: var(--color-green, #43C165);
}

/* ── Interview Overlay ── */
.iv-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10,10,10,0.5);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.iv-modal {
  background: #FAFAFA;
  border: 1px solid rgba(10,10,10,0.12);
  width: 100%;
  max-width: 580px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  font-family: var(--font-mono);
  box-shadow: 0 20px 60px rgba(10,10,10,0.25);
}

/* ── Modal Header ── */
.iv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.08);
  flex-shrink: 0;
}

.iv-agent-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.iv-avatar {
  width: 36px;
  height: 36px;
  background: rgba(10,10,10,0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  color: rgba(10,10,10,0.4);
  flex-shrink: 0;
}

.iv-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--foreground, #0A0A0A);
}

.iv-meta {
  font-size: 10px;
  color: rgba(10,10,10,0.35);
  letter-spacing: 1px;
  margin-top: 2px;
}

.iv-close {
  background: none;
  border: none;
  font-size: 16px;
  cursor: pointer;
  color: rgba(10,10,10,0.35);
  padding: 4px 8px;
  line-height: 1;
  transition: color 0.15s;
}

.iv-close:hover {
  color: rgba(10,10,10,0.8);
}

/* ── Chat Thread ── */
.iv-thread {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 200px;
  max-height: 420px;
}

.iv-empty {
  font-size: 12px;
  color: rgba(10,10,10,0.35);
  letter-spacing: 0.5px;
  line-height: 1.6;
  text-align: center;
  padding: 24px 8px;
}

.iv-qa-pair {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.iv-question,
.iv-answer {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.iv-role {
  font-size: 9px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.3);
  font-weight: 600;
}

.iv-role.agent {
  color: var(--color-green, #43C165);
}

.iv-text {
  font-size: 12px;
  line-height: 1.65;
  color: rgba(10,10,10,0.8);
  white-space: pre-wrap;
  word-break: break-word;
}

.iv-answer {
  background: rgba(10,10,10,0.02);
  border-left: 2px solid var(--color-green, #43C165);
  padding: 8px 10px;
}

.iv-share-btn {
  align-self: flex-start;
  background: none;
  border: none;
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 1px;
  color: rgba(10,10,10,0.3);
  cursor: pointer;
  padding: 2px 0;
  margin-top: 2px;
  transition: color 0.15s;
}

.iv-share-btn:hover {
  color: var(--color-orange, #FF6B1A);
}

/* ── Loading dots ── */
.iv-thinking {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 11px;
  color: rgba(10,10,10,0.35);
  letter-spacing: 1px;
  padding: 4px 0;
}

.iv-dots {
  display: flex;
  gap: 4px;
}

.iv-dots span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--color-orange, #FF6B1A);
  animation: iv-bounce 1.2s ease-in-out infinite;
}

.iv-dots span:nth-child(2) { animation-delay: 0.2s; }
.iv-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes iv-bounce {
  0%, 80%, 100% { transform: scale(0.7); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

/* ── Input Row ── */
.iv-input-row {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid rgba(10,10,10,0.08);
  flex-shrink: 0;
}

.iv-input {
  flex: 1;
  background: rgba(10,10,10,0.03);
  border: 1px solid rgba(10,10,10,0.12);
  padding: 8px 12px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--foreground, #0A0A0A);
  outline: none;
  transition: border-color 0.15s;
}

.iv-input:focus {
  border-color: var(--color-green, #43C165);
}

.iv-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.iv-send {
  background: var(--color-green, #43C165);
  border: none;
  padding: 8px 16px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1px;
  color: #fff;
  cursor: pointer;
  transition: opacity 0.15s;
}

.iv-send:hover:not(:disabled) {
  opacity: 0.85;
}

.iv-send:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* ── Error ── */
.iv-error {
  padding: 8px 16px;
  font-size: 11px;
  color: var(--color-red, #e53e3e);
  letter-spacing: 0.5px;
  border-top: 1px solid rgba(229,62,62,0.15);
  flex-shrink: 0;
}
</style>
