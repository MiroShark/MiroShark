<template>
  <div class="session-menu" :class="{ open: open }">
    <button class="trigger" type="button" @click="open = !open" :title="activeTitle">
      <span class="label">{{ activeTitle || 'Sessions' }}</span>
      <span class="caret">▾</span>
    </button>

    <div v-if="open" class="dropdown">
      <button class="item new" type="button" @click="onNew">+ New session</button>
      <div v-if="sessions.length === 0" class="empty">No sessions yet</div>
      <button
        v-for="s in sessions"
        :key="s.id"
        type="button"
        class="item"
        :class="{ active: s.id === activeId }"
        @click="onSelect(s.id)"
      >
        <div class="title">{{ s.title || '(untitled)' }}</div>
        <div class="meta">{{ formatTime(s.updated_at) }}</div>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  sessions: { type: Array, default: () => [] },
  activeId: { type: String, default: null },
})

const emit = defineEmits(['select', 'new'])

const open = ref(false)

const activeTitle = computed(() => {
  if (!props.activeId) return ''
  const found = props.sessions.find(s => s.id === props.activeId)
  return found?.title || '(untitled)'
})

function onSelect(id) {
  open.value = false
  emit('select', id)
}

function onNew() {
  open.value = false
  emit('new')
}

function formatTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return ''
    const now = new Date()
    const diffMs = now - d
    const minutes = Math.floor(diffMs / 60000)
    if (minutes < 1) return 'just now'
    if (minutes < 60) return `${minutes}m ago`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours}h ago`
    const days = Math.floor(hours / 24)
    if (days < 7) return `${days}d ago`
    return d.toLocaleDateString()
  } catch {
    return ''
  }
}
</script>

<style scoped>
.session-menu {
  position: relative;
  display: inline-block;
}
.trigger {
  background: #1a1a1a;
  color: #ddd;
  border: 1px solid #333;
  padding: 0.4rem 0.75rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  font-family: inherit;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  max-width: 240px;
}
.trigger .label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.trigger .caret { font-size: 0.7rem; color: #888; }
.dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  min-width: 280px;
  max-height: 60vh;
  overflow-y: auto;
  background: #111;
  border: 1px solid #333;
  border-radius: 4px;
  z-index: 50;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
}
.item {
  display: block;
  width: 100%;
  background: transparent;
  color: #ddd;
  border: 0;
  padding: 0.5rem 0.75rem;
  text-align: left;
  cursor: pointer;
  font-family: inherit;
  border-bottom: 1px solid #1a1a1a;
}
.item:hover { background: #1a1a1a; }
.item.active { background: #1f3a5f; }
.item.new {
  font-weight: bold;
  color: #4ade80;
}
.item .title {
  font-size: 0.85rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.item .meta {
  font-size: 0.7rem;
  color: #888;
  margin-top: 0.15rem;
}
.empty {
  padding: 0.75rem;
  color: #666;
  font-size: 0.85rem;
  font-style: italic;
}
</style>
