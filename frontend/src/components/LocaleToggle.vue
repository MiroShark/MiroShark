<template>
  <div class="locale-select-wrap">
    <select
      class="locale-select"
      :value="locale"
      aria-label="Select language"
      title="Select language"
      @change="onChange"
    >
      <option v-for="loc in locales" :key="loc" :value="loc">{{ labels[loc] }}</option>
    </select>
    <span class="locale-select-caret" aria-hidden="true">▾</span>
  </div>
</template>

<script setup>
import { useI18n, SUPPORTED_LOCALES, LOCALE_LABELS } from '../i18n'

const { locale, setLocale } = useI18n()
const locales = SUPPORTED_LOCALES
const labels = LOCALE_LABELS

function onChange(event) {
  setLocale(event.target.value)
}
</script>

<style scoped>
/* Matches the dark glossy nav-pill family on the Home view. Replaces the old
   binary EN/中 toggle with a selector now that more than two locales exist. */
.locale-select-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.locale-select {
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
  height: 36px;
  padding: 0 26px 0 12px;
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

.locale-select:hover {
  color: #ffffff;
  border-color: rgba(167, 139, 250, 0.55);
  transform: translateY(-1px);
}

.locale-select:focus-visible {
  outline: none;
  border-color: rgba(167, 139, 250, 0.75);
}

.locale-select option {
  /* Native option lists render on the OS theme; keep them legible. */
  color: #14122a;
  background: #ece8ff;
}

.locale-select-caret {
  position: absolute;
  right: 10px;
  font-size: 9px;
  color: #cfc6ff;
  pointer-events: none;
}
</style>
