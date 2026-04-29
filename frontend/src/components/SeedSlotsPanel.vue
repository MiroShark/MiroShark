<template>
  <aside class="slots-panel">
    <h3>Seed</h3>

    <div class="slot" :class="{ filled: !!seedState.topic }">
      <span class="icon">{{ seedState.topic ? '✓' : '○' }}</span>
      <div class="slot-body">
        <div class="slot-label">Topic</div>
        <div class="slot-value">{{ seedState.topic || '—' }}</div>
      </div>
    </div>

    <div class="slot" :class="{ filled: !!seedState.intent }">
      <span class="icon">{{ seedState.intent ? '✓' : '○' }}</span>
      <div class="slot-body">
        <div class="slot-label">Intent</div>
        <div class="slot-value">{{ seedState.intent || '—' }}</div>
      </div>
    </div>

    <div class="slot" :class="{ filled: stakeholdersFilled }">
      <span class="icon">{{ stakeholdersFilled ? '✓' : '○' }}</span>
      <div class="slot-body">
        <div class="slot-label">Stakeholders ({{ seedState.stakeholders.length }})</div>
        <ul v-if="seedState.stakeholders.length" class="slot-list">
          <li v-for="(s, i) in seedState.stakeholders" :key="i">
            <strong>{{ s.name }}</strong> — {{ s.role }} ({{ s.stance }})
          </li>
        </ul>
        <div v-else class="slot-value">—</div>
      </div>
    </div>

    <div class="slot" :class="{ filled: !!seedState.output_format }">
      <span class="icon">{{ seedState.output_format ? '✓' : '○' }}</span>
      <div class="slot-body">
        <div class="slot-label">Output format</div>
        <div class="slot-value">{{ seedState.output_format || '—' }}</div>
      </div>
    </div>

    <div class="slot optional" :class="{ filled: seedState.decision_branches.length > 0 }">
      <span class="icon">{{ seedState.decision_branches.length ? '✓' : '·' }}</span>
      <div class="slot-body">
        <div class="slot-label">Decision branches ({{ seedState.decision_branches.length }})</div>
        <ul v-if="seedState.decision_branches.length" class="slot-list">
          <li v-for="(b, i) in seedState.decision_branches" :key="i">
            <strong>{{ b.label }}</strong> — {{ b.description }}
          </li>
        </ul>
        <div v-else class="slot-value muted">optional</div>
      </div>
    </div>

    <div class="slot optional" :class="{ filled: seedState.contested_claims.length > 0 }">
      <span class="icon">{{ seedState.contested_claims.length ? '✓' : '·' }}</span>
      <div class="slot-body">
        <div class="slot-label">Contested claims ({{ seedState.contested_claims.length }})</div>
        <ul v-if="seedState.contested_claims.length" class="slot-list">
          <li v-for="(c, i) in seedState.contested_claims" :key="i" class="claim-row">
            <span class="claim-text">{{ c }}</span>
            <button
              type="button"
              class="claim-research-btn"
              :disabled="researchingClaim === c"
              @click="$emit('research-claim', c)"
              :title="researchingClaim === c ? 'Searching…' : 'Research this claim'"
            >{{ researchingClaim === c ? '…' : '🔍' }}</button>
          </li>
        </ul>
        <div v-else class="slot-value muted">optional</div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  seedState: { type: Object, required: true },
  researchingClaim: { type: String, default: '' },
})

const emit = defineEmits(['research-claim'])

const stakeholdersFilled = computed(() => props.seedState.stakeholders.length >= 2)
</script>

<style scoped>
.slots-panel {
  padding: 1rem;
  border-left: 1px solid #2a2a2a;
  background: #111;
  color: #ddd;
  overflow-y: auto;
  font-family: monospace;
}
.slots-panel h3 {
  margin-top: 0;
  letter-spacing: 0.1em;
}
.slot {
  display: flex;
  gap: 0.5rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid #222;
}
.slot.filled .icon { color: #4ade80; }
.slot.optional { opacity: 0.7; }
.icon {
  font-weight: bold;
  min-width: 1em;
}
.slot-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  color: #888;
}
.slot-value {
  font-size: 0.9rem;
  word-break: break-word;
}
.slot-value.muted { color: #555; font-style: italic; }
.slot-list {
  margin: 0.25rem 0 0;
  padding-left: 1rem;
  font-size: 0.85rem;
}
.claim-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
}
.claim-text { flex: 1; word-break: break-word; }
.claim-research-btn {
  background: transparent;
  border: 1px solid #333;
  color: #888;
  cursor: pointer;
  border-radius: 3px;
  padding: 0 0.4rem;
  font-size: 0.75rem;
  font-family: inherit;
  flex-shrink: 0;
}
.claim-research-btn:hover { background: #1a1a1a; color: #ccc; }
.claim-research-btn:disabled { opacity: 0.6; cursor: wait; }
</style>
