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
/* Matches the dark glossy nav-pill family on the Home view. The
   original orange Hyperstitions look is intentionally dropped. */
.locale-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 10px;
  font-family: 'Geist Mono', ui-monospace, 'SF Mono', Menlo, monospace;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: #ece8ff;
  background: linear-gradient(180deg, rgba(70, 55, 120, 0.45) 0%, rgba(20, 14, 42, 0.7) 100%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 9999px;
  cursor: pointer;
  user-select: none;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.2),
    inset 0 -1px 0 rgba(0, 0, 0, 0.4),
    0 8px 22px -10px rgba(139, 92, 246, 0.4);
  transition: border-color 180ms ease, transform 180ms ease, color 180ms ease;
}

.locale-toggle:hover {
  color: #ffffff;
  border-color: rgba(167, 139, 250, 0.55);
  transform: translateY(-1px);
}

.locale-toggle.active {
  color: #ffffff;
  border-color: rgba(167, 139, 250, 0.55);
}

.locale-toggle-flag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  padding: 2px 6px;
  border-radius: 9999px;
  font-size: 10px;
  font-weight: 700;
  color: #f4f1ff;
  background: linear-gradient(180deg, rgba(167, 139, 250, 0.35) 0%, rgba(76, 29, 149, 0.55) 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.25);
}

.locale-toggle-text {
  opacity: 0.65;
}
</style>
