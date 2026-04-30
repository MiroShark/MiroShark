<template>
  <button
    class="locale-toggle"
    :class="{ active: locale === 'zh-CN' }"
    type="button"
    :title="locale === 'zh-CN' ? 'Switch to English' : '切换到中文'"
    :aria-label="locale === 'zh-CN' ? 'Switch to English' : 'Switch to Chinese'"
    @click="toggleLocale"
  >
    <span class="locale-toggle-flag" aria-hidden="true">{{ locale === 'zh-CN' ? '中' : 'EN' }}</span>
    <span class="locale-toggle-text">{{ locale === 'zh-CN' ? 'EN' : '中' }}</span>
  </button>
</template>

<script setup>
import { useI18n } from '../i18n'

const { locale, toggleLocale } = useI18n()
</script>

<style scoped>
.locale-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  font-family: 'JetBrains Mono', 'Courier New', monospace;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: rgba(255, 255, 255, 0.8);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}

.locale-toggle:hover {
  color: #ff7a3d;
  border-color: rgba(255, 122, 61, 0.4);
  background: rgba(255, 122, 61, 0.08);
}

.locale-toggle.active {
  color: #ff7a3d;
  border-color: rgba(255, 122, 61, 0.5);
}

.locale-toggle-flag {
  display: inline-block;
  padding: 1px 5px;
  background: rgba(255, 122, 61, 0.18);
  border-radius: 2px;
  color: #ff7a3d;
  font-size: 10px;
}

.locale-toggle-text {
  opacity: 0.65;
}
</style>
