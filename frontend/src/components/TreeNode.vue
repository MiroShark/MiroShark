<template>
  <div :class="['tree-node', `type-${node.type}`]">
    <div class="card">
      <div class="card-head">
        <span class="badge">{{ typeIcon }}</span>
        <input
          v-if="editing"
          v-model="draftQuestion"
          class="question-input"
          @blur="commitQuestion"
          @keydown.enter.prevent="commitQuestion"
        />
        <span v-else class="question" @click="startEdit">{{ node.question }}</span>
      </div>

      <textarea
        :value="node.user_notes"
        class="notes"
        rows="2"
        placeholder="Add your notes…"
        @blur="onNotesBlur"
      ></textarea>

      <div v-if="node.evidence?.length" class="evidence">
        <button type="button" class="evidence-toggle" @click="evidenceOpen = !evidenceOpen">
          {{ evidenceOpen ? '▾' : '▸' }} {{ node.evidence.length }} source{{ node.evidence.length === 1 ? '' : 's' }}
        </button>
        <ul v-if="evidenceOpen" class="evidence-list">
          <li v-for="(e, i) in node.evidence" :key="i">
            <a :href="e.url" target="_blank" rel="noopener noreferrer">{{ e.title || e.url }}</a>
            <span v-if="e.fetch_error" class="status err">⚠ {{ e.fetch_error }}</span>
          </li>
        </ul>
      </div>

      <div v-if="node.summary" class="summary" v-html="renderedSummary"></div>

      <div class="actions">
        <button
          type="button"
          class="action expand"
          :disabled="busy.expand"
          @click="$emit('expand', node.id)"
        >{{ busy.expand ? 'Expanding…' : 'Expand ▾' }}</button>
        <button
          type="button"
          class="action research"
          :disabled="busy.research"
          @click="$emit('research', node.id)"
        >{{ busy.research ? 'Researching…' : 'Research 🔍' }}</button>
        <button
          v-if="node.evidence?.length"
          type="button"
          class="action synthesize"
          :disabled="busy.synthesize"
          @click="$emit('synthesize', node.id)"
        >{{ busy.synthesize ? 'Synthesizing…' : (node.summary ? 'Re-synthesize ✨' : 'Synthesize ✨') }}</button>
      </div>
    </div>

    <div v-if="node.children?.length" class="children">
      <TreeNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :busy-map="busyMap"
        @expand="$emit('expand', $event)"
        @research="$emit('research', $event)"
        @update-node="$emit('update-node', $event)"
        @synthesize="$emit('synthesize', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  node: { type: Object, required: true },
  busyMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['expand', 'research', 'update-node', 'synthesize'])

const editing = ref(false)
const draftQuestion = ref('')
const evidenceOpen = ref(false)

const typeIcon = computed(() => {
  switch (props.node.type) {
    case 'central': return '🎯'
    case 'upstream': return '⬆'
    case 'downstream': return '⬇'
    case 'analogy': return '↔'
    default: return '✦'
  }
})

const busy = computed(() => props.busyMap?.[props.node.id] || {})

const renderedSummary = computed(() => props.node.summary ? marked.parse(props.node.summary) : '')

function startEdit() {
  draftQuestion.value = props.node.question
  editing.value = true
}

function commitQuestion() {
  const next = draftQuestion.value.trim()
  if (next && next !== props.node.question) {
    emit('update-node', { node_id: props.node.id, fields: { question: next } })
  }
  editing.value = false
}

function onNotesBlur(event) {
  const next = event.target.value
  if (next !== props.node.user_notes) {
    emit('update-node', { node_id: props.node.id, fields: { user_notes: next } })
  }
}
</script>

<style scoped>
.tree-node { margin: 0.5rem 0; }
.card {
  background: #161616;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  padding: 0.75rem;
}
.tree-node.type-central > .card {
  border-color: #4ade80;
  background: #0c2a14;
}
.tree-node.type-upstream > .card { border-color: #60a5fa; }
.tree-node.type-downstream > .card { border-color: #f59e0b; }
.tree-node.type-analogy > .card { border-color: #c084fc; }

.card-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.4rem;
}
.badge {
  font-size: 1rem;
  width: 1.5em;
  text-align: center;
}
.question {
  flex: 1;
  font-size: 0.95rem;
  font-weight: 500;
  color: #eee;
  cursor: text;
}
.question:hover { background: #1f1f1f; }
.question-input {
  flex: 1;
  background: #0d0d0d;
  color: #eee;
  border: 1px solid #4ade80;
  border-radius: 3px;
  padding: 0.3rem 0.4rem;
  font-size: 0.95rem;
  font-family: inherit;
}
.notes {
  display: block;
  width: 100%;
  background: #0d0d0d;
  color: #ccc;
  border: 1px solid #2a2a2a;
  border-radius: 3px;
  padding: 0.3rem;
  font-size: 0.8rem;
  resize: vertical;
  font-family: inherit;
  margin-bottom: 0.4rem;
}
.evidence {
  margin: 0.4rem 0;
  font-size: 0.8rem;
}
.evidence-toggle {
  background: transparent;
  border: 0;
  color: #80b4ff;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.8rem;
  padding: 0;
}
.evidence-list {
  margin: 0.25rem 0 0;
  padding-left: 1.25rem;
  color: #aaa;
}
.evidence-list a { color: #80b4ff; text-decoration: none; }
.evidence-list a:hover { text-decoration: underline; }
.evidence-list .err { color: #f87171; margin-left: 0.4rem; font-size: 0.75rem; }
.actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}
.action {
  padding: 0.3rem 0.6rem;
  background: #2a2a2a;
  color: #ddd;
  border: 1px solid #3a3a3a;
  border-radius: 3px;
  cursor: pointer;
  font-size: 0.75rem;
  font-family: inherit;
}
.action:hover { background: #333; }
.action:disabled { opacity: 0.5; cursor: wait; }

.children {
  margin-left: 1.5rem;
  padding-left: 0.75rem;
  border-left: 1px solid #222;
}
.summary {
  background: #0c1a2c;
  border-left: 3px solid #80b4ff;
  padding: 0.6rem 0.75rem;
  margin: 0.5rem 0;
  border-radius: 0 4px 4px 0;
  font-size: 0.85rem;
  line-height: 1.5;
  color: #e0e8f0;
}
.summary :deep(p) { margin: 0.4em 0; }
.summary :deep(strong) { color: #fff; }
.summary :deep(a) { color: #80b4ff; }
.summary :deep(code) {
  background: #1a2a3a;
  padding: 0 0.25em;
  border-radius: 3px;
}
.action.synthesize {
  background: #2a2a4a;
  color: #d6d6f5;
  border-color: #3a3a6a;
}
.action.synthesize:hover { background: #353559; }
</style>
