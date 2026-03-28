<template>
  <Teleport to="body">
    <TransitionGroup name="toast" tag="div" class="toast-container">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="toast"
        :class="toast.type"
        @click="remove(toast.id)"
      >
        <span class="toast-icon">{{ icons[toast.type] }}</span>
        <span class="toast-msg">{{ toast.message }}</span>
      </div>
    </TransitionGroup>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'

const toasts = ref([])
let nextId = 0

const icons = {
  error: 'x',
  success: '+',
  warning: '!',
  info: 'i',
}

const add = (message, type = 'info', duration = 5000) => {
  const id = nextId++
  toasts.value.push({ id, message, type })
  if (duration > 0) {
    setTimeout(() => remove(id), duration)
  }
}

const remove = (id) => {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

defineExpose({ add, remove })
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 400px;
}

.toast {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-family: 'Space Grotesk', system-ui, sans-serif;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  background: #333;
  color: #fff;
}

.toast.error { background: #c62828; }
.toast.success { background: #2e7d32; }
.toast.warning { background: #e65100; }
.toast.info { background: #1565c0; }

.toast-icon {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 14px;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(255,255,255,0.2);
  flex-shrink: 0;
}

.toast-msg { line-height: 1.4; }

.toast-enter-active { transition: all 0.3s ease; }
.toast-leave-active { transition: all 0.2s ease; }
.toast-enter-from { opacity: 0; transform: translateX(30px); }
.toast-leave-to { opacity: 0; transform: translateX(30px); }
</style>
