<template>
  <div class="foresight-overlay" @click.self="$emit('close')">
    <div class="foresight-modal education-modal">
      <header class="foresight-header">
        <div>
          <h2>Education/debunking plan</h2>
          <p class="modal-subtitle">{{ educationPlan?.questions?.length || 0 }} questions · {{ educationInfographicPlan?.sequence?.length || 0 }} generic lesson slides</p>
        </div>
        <button type="button" class="close" @click="$emit('close')">×</button>
      </header>
      <div class="education-body">
        <section v-if="educationPlan?.claims?.length" class="education-section">
          <h3>Claims to unpack</h3>
          <div v-for="claim in educationPlan.claims" :key="claim.claim_id" class="education-card">
            <strong>{{ claim.surface_claim }}</strong>
            <span>{{ claim.claim_type }} · verdict: {{ claim.verdict }}</span>
            <em v-if="claim.normalizations_needed?.length">Normalize: {{ claim.normalizations_needed.join(', ') }}</em>
          </div>
        </section>
        <section v-if="educationPlan?.normalizations?.length" class="education-section">
          <h3>Normalized comparisons</h3>
          <div v-for="norm in educationPlan.normalizations" :key="norm.normalization_id" class="education-card normalization-card">
            <strong>{{ norm.label }}</strong>
            <p>{{ norm.plain_english }}</p>
            <div class="normalization-grid">
              <span>Raw total: {{ formatBillions(norm.comparison?.start?.nominal_total) }} → {{ formatBillions(norm.comparison?.end?.nominal_total) }}</span>
              <span v-if="norm.comparison?.start?.per_capita && norm.comparison?.end?.per_capita">Per resident: {{ formatThousands(norm.comparison.start.per_capita) }} → {{ formatThousands(norm.comparison.end.per_capita) }}</span>
              <span v-if="norm.comparison?.changes?.population_growth_rate !== undefined">Population: +{{ formatRate(norm.comparison.changes.population_growth_rate) }}</span>
              <span v-if="norm.comparison?.changes?.per_capita_ratio">Per-resident ratio: {{ norm.comparison.changes.per_capita_ratio.toFixed(1) }}×</span>
            </div>
            <em>Views: {{ norm.views?.join(', ') }}</em>
          </div>
        </section>
        <section class="education-section">
          <h3>Question sequence</h3>
          <ol class="education-steps">
            <li v-for="q in educationPlan?.questions || []" :key="q.question_id">
              <strong>{{ q.question }}</strong>
              <span>{{ q.question_type }} → {{ q.output_slide_type }}</span>
              <em>Needs: {{ q.facts_needed.join(', ') }}</em>
            </li>
          </ol>
        </section>
        <section class="education-section">
          <h3>Lesson beats</h3>
          <div v-for="beat in educationPlan?.lesson_beats || []" :key="beat.slide_id" class="education-card">
            <strong>{{ beat.title }}</strong>
            <span>{{ beat.slide_id }} · {{ beat.slide_type }}</span>
            <p>{{ beat.teaching_goal }}</p>
          </div>
        </section>
      </div>
      <footer class="foresight-footer">
        <button type="button" class="secondary" @click="$emit('copy-json')">Copy JSON</button>
        <button type="button" class="secondary" @click="$emit('download-json')">Download JSON</button>
        <button type="button" class="primary" :disabled="planning" @click="$emit('regenerate')">{{ planning ? 'Regenerating…' : 'Regenerate' }}</button>
        <button type="button" class="secondary" @click="$emit('close')">Close</button>
      </footer>
    </div>
  </div>
</template>

<script setup>
defineProps({
  educationPlan: { type: Object, default: null },
  educationInfographicPlan: { type: Object, default: null },
  planning: { type: Boolean, default: false },
})

defineEmits(['close', 'copy-json', 'download-json', 'regenerate'])

function formatRate(rate) {
  const value = Number(rate)
  if (!Number.isFinite(value)) return '—'
  return `${(value * 100).toFixed(0)}%`
}

function formatBillions(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `$${number.toLocaleString(undefined, { maximumFractionDigits: 1 })}b`
}

function formatThousands(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `$${(number * 1000).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}
</script>

<style>
.education-modal { max-width: 980px; }
.education-body {
  padding: 1rem 1.25rem;
  overflow: auto;
  color: #d7dee8;
}
.education-section { margin-bottom: 1.1rem; }
.education-section h3 { margin: 0 0 0.55rem; color: #dbeafe; }
.education-card, .education-steps li {
  margin-bottom: 0.55rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid #28384d;
  border-radius: 8px;
  background: #0b1220;
}
.education-card strong, .education-steps strong { display: block; color: #fff; }
.education-card span, .education-card em, .education-steps span, .education-steps em {
  display: block;
  margin-top: 0.25rem;
  color: #94a3b8;
  font-size: 0.8rem;
}
.education-card p { margin: 0.35rem 0 0; color: #cbd5e1; }
.normalization-card { border-color: #315c7d; background: #071827; }
.normalization-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.45rem;
  margin-top: 0.65rem;
}
.normalization-grid span {
  padding: 0.45rem 0.55rem;
  border: 1px solid #29445e;
  border-radius: 7px;
  background: #0f2635;
  color: #d7efff;
}
</style>
