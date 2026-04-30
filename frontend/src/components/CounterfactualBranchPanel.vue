<template>
  <div class="cf-panel">
    <div class="cf-header">
      <div class="cf-title">
        <span class="cf-icon">⤷</span>
        <span class="cf-label">{{ $tr('COUNTERFACTUAL BRANCH', '反事实分支') }}</span>
      </div>
      <span class="cf-hint">
        {{ $tr('Fork this simulation from round N with a narrative injection. Preserves the agent population; the runner promotes your injection into a director event when round', '从第 N 轮派生此模拟,并注入一段叙事。保留智能体人群;当达到第') }} {{ triggerRound || 'N' }} {{ $tr('arrives.', '轮时,运行器会将你的注入提升为导演事件。') }}
      </span>
    </div>

    <!-- Preset-branch dropdown (when the source template declared them) -->
    <div v-if="presetBranches.length" class="cf-preset-row">
      <label class="cf-preset-label">{{ $tr('Preset', '预设') }}</label>
      <select
        class="cf-preset-select"
        :value="selectedPresetId"
        @change="applyPreset($event.target.value)"
      >
        <option value="">{{ $tr('— custom —', '— 自定义 —') }}</option>
        <option
          v-for="b in presetBranches"
          :key="b.id"
          :value="b.id"
        >{{ b.label }} (r{{ b.trigger_round }})</option>
      </select>
    </div>

    <!-- Trigger round picker -->
    <div class="cf-form-row">
      <label class="cf-form-label">{{ $tr('Trigger round', '触发轮次') }}</label>
      <input
        type="number"
        class="cf-form-input cf-form-input--narrow"
        :min="0"
        :max="totalRounds || 999"
        v-model.number="triggerRound"
        :disabled="busy"
      />
      <span class="cf-form-meta">
        {{ $tr('of', '共') }} {{ totalRounds || '?' }} · {{ $tr('currently at round', '当前在第') }} {{ currentRound }}
      </span>
    </div>

    <!-- Short label -->
    <div class="cf-form-row">
      <label class="cf-form-label">{{ $tr('Label', '标签') }}</label>
      <input
        type="text"
        class="cf-form-input"
        v-model="label"
        maxlength="80"
        :placeholder="$tr('e.g. CEO resigns', '例如 CEO 辞职')"
        :disabled="busy"
      />
    </div>

    <!-- Injection text -->
    <div class="cf-form-row cf-form-row--stack">
      <label class="cf-form-label">{{ $tr('Injection (breaking-news style)', '注入内容(突发新闻风格)') }}</label>
      <textarea
        class="cf-form-textarea"
        v-model="injectionText"
        maxlength="2000"
        :placeholder="$tr(`The board has just announced the CEO's resignation, effective immediately. The CFO steps in as interim lead.`, '董事会刚刚宣布 CEO 立即辞职,CFO 作为临时负责人接任。')"
        rows="4"
        :disabled="busy"
      ></textarea>
      <div class="cf-form-meta cf-form-meta--right">
        {{ injectionText.length }}/2000
      </div>
    </div>

    <div v-if="error" class="cf-error">{{ error }}</div>
    <div v-if="result" class="cf-result">
      {{ $tr('Branch created:', '分支已创建:') }} <code>{{ result.simulation_id }}</code>
      <span v-if="result.config_diff?.counterfactual?.label">
        · "{{ result.config_diff.counterfactual.label }}"
      </span>
      <button class="cf-open-btn" @click="openBranch">{{ $tr('Open →', '打开 →') }}</button>
    </div>

    <div class="cf-actions">
      <button
        class="cf-cancel"
        @click="$emit('close')"
        :disabled="busy"
      >{{ $tr('Cancel', '取消') }}</button>
      <button
        class="cf-submit"
        :disabled="!canSubmit || busy"
        @click="submit"
      >
        <span v-if="busy" class="cf-spinner"></span>
        {{ busy ? $tr('Forking…', '派生中…') : $tr('Fork branch →', '派生分支 →') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { branchCounterfactual } from '../api/simulation'
import { tr } from '../i18n'

const props = defineProps({
  simulationId: { type: String, required: true },
  currentRound: { type: Number, default: 0 },
  totalRounds: { type: Number, default: 0 },
  // Optional: counterfactual_branches carried from the source template.
  presetBranches: { type: Array, default: () => [] },
})

defineEmits(['close'])

const router = useRouter()

const selectedPresetId = ref('')
const triggerRound = ref(Math.max(props.currentRound + 1, 0))
const label = ref('')
const injectionText = ref('')
const busy = ref(false)
const error = ref('')
const result = ref(null)

const canSubmit = computed(() => {
  const t = Number(triggerRound.value)
  return (
    Number.isFinite(t) &&
    t >= 0 &&
    injectionText.value.trim().length >= 16 &&
    label.value.trim().length >= 2
  )
})

const applyPreset = (id) => {
  selectedPresetId.value = id
  const preset = props.presetBranches.find(b => b.id === id)
  if (!preset) return
  triggerRound.value = preset.trigger_round ?? triggerRound.value
  label.value = preset.label || ''
  injectionText.value = preset.injection || preset.description || ''
}

const submit = async () => {
  if (!canSubmit.value) return
  busy.value = true
  error.value = ''
  result.value = null
  try {
    const res = await branchCounterfactual(props.simulationId, {
      injectionText: injectionText.value.trim(),
      triggerRound: Number(triggerRound.value),
      label: label.value.trim(),
      branchId: selectedPresetId.value || undefined,
    })
    if (!res.success) {
      error.value = res.error || tr('Branch failed.', '分支创建失败。')
      return
    }
    result.value = res.data
  } catch (err) {
    error.value = err?.response?.data?.error || err?.message || tr('Branch failed.', '分支创建失败。')
  } finally {
    busy.value = false
  }
}

const openBranch = () => {
  if (!result.value?.simulation_id) return
  // Branch produces a READY simulation (profiles + config copied from parent).
  // Jump straight into the running view — same treatment HistoryDatabase.vue
  // gives a fresh fork. The previous 'Process' / projectId route landed the
  // user on the project graph-build flow (step 2/4).
  router.push({ name: 'SimulationRun', params: { simulationId: result.value.simulation_id } })
}

onMounted(() => {
  // Auto-apply the first preset if one exists — zero-friction path.
  if (props.presetBranches.length && !injectionText.value) {
    applyPreset(props.presetBranches[0].id)
  }
})
</script>

<style scoped>
/* ── Container — mirrors .influence-leaderboard base (Space Mono, light bg) ── */
.cf-panel {
  display: flex;
  flex-direction: column;
  gap: 0;
  background: var(--background);
  border: 1px solid rgba(10, 10, 10, 0.08);
  font-family: var(--font-mono);
}

/* ── Header — mirrors .lb-header ── */
.cf-header {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(10, 10, 10, 0.08);
  flex-shrink: 0;
}

.cf-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cf-icon {
  font-size: 14px;
  color: var(--color-orange);
}

.cf-label {
  font-size: 12px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: rgba(10, 10, 10, 0.5);
}

.cf-hint {
  font-size: 11px;
  line-height: 1.5;
  color: rgba(10, 10, 10, 0.5);
  letter-spacing: 0.3px;
}

/* ── Form rows ── */
.cf-preset-row,
.cf-form-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid rgba(10, 10, 10, 0.05);
}

.cf-form-row--stack {
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
}

.cf-preset-label,
.cf-form-label {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: rgba(10, 10, 10, 0.4);
  width: 120px;
  flex-shrink: 0;
}

.cf-form-row--stack .cf-form-label {
  width: 100%;
}

.cf-preset-select,
.cf-form-input,
.cf-form-textarea {
  font-family: var(--font-mono);
  font-size: 12px;
  padding: 6px 10px;
  border: 1px solid rgba(10, 10, 10, 0.12);
  background: #fff;
  color: var(--foreground);
  outline: none;
  flex: 1;
  min-width: 0;
  transition: border-color 0.15s;
}

.cf-form-input--narrow {
  max-width: 100px;
  flex: none;
}

.cf-form-textarea {
  min-height: 90px;
  resize: vertical;
  line-height: 1.55;
}

.cf-form-input:focus,
.cf-form-textarea:focus,
.cf-preset-select:focus {
  border-color: var(--color-orange);
}

.cf-form-meta {
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10, 10, 10, 0.4);
  letter-spacing: 1px;
}

.cf-form-meta--right {
  text-align: right;
  padding: 0 16px 10px;
}

/* ── Error / result states — mirrors .iv-error / .iv-answer ── */
.cf-error {
  margin: 10px 16px 0;
  padding: 8px 10px;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.5;
  color: var(--color-red);
  background: rgba(255, 68, 68, 0.06);
  border-left: 2px solid var(--color-red);
  letter-spacing: 0.3px;
}

.cf-result {
  margin: 10px 16px 0;
  padding: 8px 10px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10, 10, 10, 0.8);
  background: rgba(67, 193, 101, 0.06);
  border-left: 2px solid var(--color-green);
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  letter-spacing: 0.3px;
}

.cf-result code {
  background: rgba(10, 10, 10, 0.04);
  padding: 1px 4px;
  font-size: 10px;
  color: var(--foreground);
}

.cf-open-btn {
  margin-left: auto;
  background: none;
  border: 1px solid var(--color-green);
  color: var(--color-green);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 1px;
  padding: 3px 10px;
  cursor: pointer;
  text-transform: uppercase;
  transition: all 0.15s;
}

.cf-open-btn:hover {
  background: var(--color-green);
  color: var(--color-white);
}

/* ── Actions row — matches the Step3 action-btn language ── */
.cf-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  padding: 12px 16px;
  border-top: 1px solid rgba(10, 10, 10, 0.05);
}

.cf-cancel,
.cf-submit {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 2.5px;
  text-transform: uppercase;
  padding: 8px 16px;
  border: 2px solid rgba(10, 10, 10, 0.12);
  cursor: pointer;
  transition: all 0.1s ease;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.cf-cancel {
  background: transparent;
  color: rgba(10, 10, 10, 0.4);
}

.cf-cancel:hover:not(:disabled) {
  border-color: rgba(10, 10, 10, 0.3);
  color: rgba(10, 10, 10, 0.7);
}

.cf-submit {
  background: var(--color-black);
  color: var(--color-white);
  border-color: var(--color-black);
}

.cf-submit:hover:not(:disabled) {
  opacity: 0.9;
}

.cf-submit:disabled,
.cf-cancel:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* ── Spinner — dark-track on black submit, light track on cancel ── */
.cf-spinner {
  width: 10px;
  height: 10px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: var(--color-orange);
  border-radius: 50%;
  animation: cf-spin 0.8s linear infinite;
}

@keyframes cf-spin {
  to { transform: rotate(360deg); }
}
</style>
