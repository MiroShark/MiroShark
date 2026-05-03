<template>
  <div class="research-progress-banner" role="status" aria-live="polite">
    <span class="spinner-dot"></span>
    <span class="spinner-dot"></span>
    <span class="spinner-dot"></span>
    <span class="progress-text">
      {{ label }} {{ progress.current }} of {{ progress.total }}:
      <span class="progress-question">"{{ progress.label }}"</span>
    </span>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  progress: { type: Object, required: true },
})
</script>

<style>
.research-progress-banner { display: flex; align-items: center; gap: 0.5rem; padding: 0.6rem 1.25rem; background: #1a2a3a; border-bottom: 1px solid #2a4a6a; color: #b8d6f5; font-size: 0.85rem; }
.research-progress-banner .spinner-dot { width: 6px; height: 6px; border-radius: 50%; background: #80b4ff; animation: progressPulse 1.4s infinite ease-in-out both; }
.research-progress-banner .spinner-dot:nth-child(1) { animation-delay: -0.32s; }
.research-progress-banner .spinner-dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes progressPulse { 0%, 80%, 100% { opacity: 0.2; } 40% { opacity: 1; } }
.progress-text { margin-left: 0.5rem; }
.progress-question { font-style: italic; color: #aaa; margin-left: 0.25rem; }
</style>
