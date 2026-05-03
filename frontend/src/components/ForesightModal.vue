<template>
  <div class="foresight-overlay" @click.self="$emit('close')">
    <div class="foresight-modal">
      <header class="foresight-header">
        <h2>Foresight document</h2>
        <button type="button" class="close" @click="$emit('close')">×</button>
      </header>
      <div class="foresight-body" v-html="renderedForesight"></div>
      <footer class="foresight-footer">
        <button type="button" class="secondary" @click="$emit('copy')">Copy markdown</button>
        <button type="button" class="secondary" @click="$emit('download')">Download .md</button>
        <button type="button" class="primary" :disabled="compiling" @click="$emit('regenerate')">{{ compiling ? 'Regenerating…' : 'Regenerate' }}</button>
        <button type="button" class="secondary" @click="$emit('close')">Close</button>
      </footer>
    </div>
  </div>
</template>

<script setup>
defineProps({
  renderedForesight: { type: String, default: '' },
  compiling: { type: Boolean, default: false },
})

defineEmits(['close', 'copy', 'download', 'regenerate'])
</script>

<style>
.foresight-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.foresight-modal {
  width: min(900px, 90vw);
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  background: #111;
  border: 1px solid #333;
  border-radius: 6px;
  overflow: hidden;
}
.foresight-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid #222;
}
.foresight-header h2 { margin: 0; font-size: 1rem; letter-spacing: 0.05em; }
.foresight-header .close {
  background: transparent;
  color: #888;
  border: 0;
  font-size: 1.5rem;
  cursor: pointer;
  line-height: 1;
}
.foresight-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem 1.5rem;
  line-height: 1.55;
}
.foresight-body h1,
.foresight-body h2,
.foresight-body h3 { margin-top: 1.25em; }
.foresight-body h1 { font-size: 1.4rem; color: #f5e8d6; }
.foresight-body h2 {
  font-size: 1.15rem;
  color: #e5e5e5;
  border-bottom: 1px solid #222;
  padding-bottom: 0.25rem;
}
.foresight-body h3 { font-size: 1rem; color: #ddd; }
.foresight-body p { margin: 0.6em 0; }
.foresight-body ul,
.foresight-body ol { padding-left: 1.5rem; }
.foresight-body li { margin: 0.25em 0; }
.foresight-body strong { color: #fff; }
.foresight-body a { color: #80b4ff; }

.foresight-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 0.75rem 1.25rem;
  border-top: 1px solid #222;
}
.foresight-footer button {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid #444;
  font-family: inherit;
}
.foresight-footer .primary { background: #4ade80; color: #052e16; font-weight: bold; }
.foresight-footer .secondary { background: #333; color: #ddd; }
.foresight-footer button:disabled { opacity: 0.5; cursor: not-allowed; }
.foresight-footer .tiny,
.tiny {
  padding: 0.3rem 0.55rem;
  font-size: 0.75rem;
}
</style>
