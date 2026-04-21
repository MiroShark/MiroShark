<template>
  <div class="cf-panel">
    <div class="cf-header">
      <div class="cf-title">
        <span class="cf-icon">⤷</span>
        <span class="cf-label">COUNTERFACTUAL BRANCH</span>
      </div>
      <span class="cf-hint">
        Fork this simulation from round N with a narrative injection.
        Preserves the agent population; the runner promotes your injection into
        a director event when round {{ triggerRound || 'N' }} arrives.
      </span>
    </div>

    <!-- Preset-branch dropdown (when the source template declared them) -->
    <div v-if="presetBranches.length" class="cf-preset-row">
      <label class="cf-preset-label">Preset</label>
      <select
        class="cf-preset-select"
        :value="selectedPresetId"
        @change="applyPreset($event.target.value)"
      >
        <option value="">— custom —</option>
        <option
          v-for="b in presetBranches"
          :key="b.id"
          :value="b.id"
        >{{ b.label }} (r{{ b.trigger_round }})</option>
      </select>
    </div>

    <!-- Trigger round picker -->
    <div class="cf-form-row">
      <label class="cf-form-label">Trigger round</label>
      <input
        type="number"
        class="cf-form-input cf-form-input--narrow"
        :min="0"
        :max="totalRounds || 999"
        v-model.number="triggerRound"
        :disabled="busy"
      />
      <span class="cf-form-meta">
        of {{ totalRounds || '?' }} · currently at round {{ currentRound }}
      </span>
    </div>

    <!-- Short label -->
    <div class="cf-form-row">
      <label class="cf-form-label">Label</label>
      <input
        type="text"
        class="cf-form-input"
        v-model="label"
        maxlength="80"
        placeholder="e.g. CEO resigns"
        :disabled="busy"
      />
    </div>

    <!-- Injection text -->
    <div class="cf-form-row cf-form-row--stack">
      <label class="cf-form-label">Injection (breaking-news style)</label>
      <textarea
        class="cf-form-textarea"
        v-model="injectionText"
        maxlength="2000"
        placeholder="The board has just announced the CEO's resignation, effective immediately. The CFO steps in as interim lead."
        rows="4"
        :disabled="busy"
      ></textarea>
      <div class="cf-form-meta cf-form-meta--right">
        {{ injectionText.length }}/2000
      </div>
    </div>

    <div v-if="error" class="cf-error">{{ error }}</div>
    <div v-if="result" class="cf-result">
      Branch created: <code>{{ result.simulation_id }}</code>
      <span v-if="result.config_diff?.counterfactual?.label">
        · "{{ result.config_diff.counterfactual.label }}"
      </span>
      <button class="cf-open-btn" @click="openBranch">Open →</button>
    </div>

    <div class="cf-actions">
      <button
        class="cf-cancel"
        @click="$emit('close')"
        :disabled="busy"
      >Cancel</button>
      <button
        class="cf-submit"
        :disabled="!canSubmit || busy"
        @click="submit"
      >
        <span v-if="busy" class="cf-spinner"></span>
        {{ busy ? 'Forking…' : 'Fork branch →' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { branchCounterfactual } from '../api/simulation'

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
      error.value = res.error || 'Branch failed.'
      return
    }
    result.value = res.data
  } catch (err) {
    error.value = err?.response?.data?.error || err?.message || 'Branch failed.'
  } finally {
    busy.value = false
  }
}

const openBranch = () => {
  if (!result.value?.simulation_id) return
  router.push({ name: 'Process', params: { projectId: result.value.simulation_id } })
}

onMounted(() => {
  // Auto-apply the first preset if one exists — zero-friction path.
  if (props.presetBranches.length && !injectionText.value) {
    applyPreset(props.presetBranches[0].id)
  }
})
</script>

<style scoped>
.cf-panel {
  background: #FAFAFA;
  border: 2px solid rgba(10, 10, 10, 0.08);
  padding: 20px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.cf-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(10, 10, 10, 0.08);
}

.cf-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
}

.cf-icon {
  color: #FF6B1A;
  font-size: 16px;
}

.cf-label {
  color: #0A0A0A;
}

.cf-hint {
  font-size: 12px;
  color: rgba(10, 10, 10, 0.5);
  line-height: 1.5;
}

.cf-preset-row,
.cf-form-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cf-form-row--stack {
  flex-direction: column;
  align-items: stretch;
  gap: 4px;
}

.cf-preset-label,
.cf-form-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: rgba(10, 10, 10, 0.5);
  letter-spacing: 1px;
  text-transform: uppercase;
  width: 130px;
  flex-shrink: 0;
}

.cf-form-row--stack .cf-form-label {
  width: 100%;
  margin-bottom: 2px;
}

.cf-preset-select,
.cf-form-input,
.cf-form-textarea {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  padding: 6px 10px;
  border: 1px solid rgba(10, 10, 10, 0.12);
  background: #fff;
  color: #0A0A0A;
  outline: none;
  flex: 1;
  min-width: 0;
}

.cf-form-input--narrow {
  max-width: 100px;
  flex: none;
}

.cf-form-textarea {
  min-height: 90px;
  resize: vertical;
  line-height: 1.5;
  font-family: var(--font-display);
  font-size: 13px;
}

.cf-form-input:focus,
.cf-form-textarea:focus,
.cf-preset-select:focus {
  border-color: #FF6B1A;
}

.cf-form-meta {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: rgba(10, 10, 10, 0.4);
}

.cf-form-meta--right {
  text-align: right;
}

.cf-error {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #CC0000;
  background: rgba(204, 0, 0, 0.05);
  padding: 6px 10px;
  border-left: 2px solid #CC0000;
}

.cf-result {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #2d8a3f;
  background: rgba(67, 193, 101, 0.06);
  padding: 8px 10px;
  border-left: 2px solid #2d8a3f;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.cf-result code {
  background: rgba(10, 10, 10, 0.04);
  padding: 1px 4px;
}

.cf-open-btn {
  margin-left: auto;
  background: #2d8a3f;
  color: #fff;
  border: none;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  cursor: pointer;
  letter-spacing: 1px;
}

.cf-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 4px;
}

.cf-cancel,
.cf-submit {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 600;
  padding: 8px 16px;
  cursor: pointer;
  letter-spacing: 1px;
  text-transform: uppercase;
  transition: all 0.15s;
}

.cf-cancel {
  background: transparent;
  border: 1px solid rgba(10, 10, 10, 0.15);
  color: rgba(10, 10, 10, 0.7);
}

.cf-cancel:hover:not(:disabled) {
  border-color: rgba(10, 10, 10, 0.35);
}

.cf-submit {
  background: #0A0A0A;
  color: #fff;
  border: 1px solid #0A0A0A;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.cf-submit:hover:not(:disabled) {
  background: #FF6B1A;
  border-color: #FF6B1A;
}

.cf-submit:disabled,
.cf-cancel:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.cf-spinner {
  width: 10px;
  height: 10px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: cf-spin 0.8s linear infinite;
}

@keyframes cf-spin {
  to { transform: rotate(360deg); }
}
</style>
