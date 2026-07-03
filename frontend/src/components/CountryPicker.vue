<template>
  <div v-if="countries.length > 0" class="country-picker">
    <label class="cp-row">
      <span class="cp-label">{{ $tr('Demographic country', '人口国别', { de: 'Demografisches Land', fr: 'Pays démographique' }) }}</span>
      <select
        class="cp-select"
        v-model="selectedCode"
        :disabled="disabled"
        @change="onCountryChange"
        :title="$tr('Anchor each agent in a real census-grounded persona row from the chosen country (optional)', '可选:让每个智能体的人物画像基于所选国家真实的人口统计数据', { de: 'Jeden Agenten optional in einer realen volkszählungsbasierten Persona des gewählten Landes verankern (optional)', fr: `Ancrez chaque agent dans une ligne de persona issue d'un recensement réel du pays choisi (optionnel)` })"
      >
        <option value="">{{ $tr('None (graph-only)', '不启用(仅用图谱)', { de: 'Keine (nur Graph)', fr: 'Aucun (graphe uniquement)' }) }}</option>
        <option v-for="c in countries" :key="c.code" :value="c.code">
          {{ c.flag_emoji }} {{ c.name }}
        </option>
      </select>
    </label>

    <div v-if="selectedCode && geographyValues.length > 0" class="cp-geography">
      <div class="cp-geo-header">
        <span class="cp-geo-label">{{ geographyLabel }}</span>
        <button
          type="button"
          class="cp-geo-clear"
          v-if="selectedGeography.length > 0"
          :disabled="disabled"
          @click="selectedGeography = []; emitValue()"
        >{{ $tr('Clear', '清除', { de: 'Zurücksetzen', fr: 'Effacer' }) }}</button>
      </div>
      <div class="cp-chips">
        <button
          v-for="v in geographyValues"
          :key="v"
          type="button"
          class="cp-chip"
          :class="{ active: selectedGeography.includes(v) }"
          :disabled="disabled"
          @click="toggleGeography(v)"
        >{{ v }}</button>
      </div>
      <p v-if="selectedGeography.length === 0" class="cp-hint">
        {{ $tr('No filter → sample across all regions.', '不选 → 在所有地区抽样', { de: 'Kein Filter → Stichprobe aus allen Regionen.', fr: 'Aucun filtre → échantillon sur toutes les régions.' }) }}
      </p>
    </div>

    <p v-if="selectedCode" class="cp-foot-hint">
      {{ $tr('First run downloads the Nemotron dataset (~hundreds of MB) into the backend cache.',
        '首次运行会将 Nemotron 数据集(数百 MB)下载到后端缓存。', { de: 'Beim ersten Ausführen wird der Nemotron-Datensatz (~mehrere hundert MB) in den Backend-Cache heruntergeladen.', fr: 'Le premier lancement télécharge le jeu de données Nemotron (~centaines de Mo) dans le cache backend.' }) }}
    </p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { listCountries, getCountry } from '../api/countries'
import { tr } from '../i18n'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({ country: null, demographic_filters: null })
  },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue'])

const countries = ref([])
const activeCountry = ref(null)
const selectedCode = ref(props.modelValue?.country || '')

// Per-country geography options, lazily loaded on first selection and cached.
const geoCache = ref({})
const selectedGeography = ref(
  Array.isArray(props.modelValue?.demographic_filters?.geography_values)
    ? [...props.modelValue.demographic_filters.geography_values]
    : []
)

const geographyValues = computed(() => geoCache.value[selectedCode.value]?.values || [])
const geographyLabel = computed(() => geoCache.value[selectedCode.value]?.label || tr('Geography', '地区', { de: 'Geografie', fr: 'Géographie' }))

onMounted(async () => {
  try {
    const res = await listCountries()
    if (res?.success) {
      countries.value = (res.data?.countries || []).filter(c => c.available !== false)
      activeCountry.value = res.data?.active_country || null
      // Preselect the env-default when the form doesn't already carry one.
      if (!selectedCode.value && activeCountry.value) {
        selectedCode.value = activeCountry.value
        await loadCountryDetail(activeCountry.value)
        emitValue()
      } else if (selectedCode.value) {
        await loadCountryDetail(selectedCode.value)
      }
    }
  } catch (err) {
    // Endpoint missing on older backends — silently degrade to "feature off".
    countries.value = []
  }
})

async function loadCountryDetail(code) {
  if (!code || geoCache.value[code]) return
  try {
    const res = await getCountry(code)
    if (res?.success) {
      geoCache.value[code] = {
        label: res.data?.geography?.label || tr('Geography', '地区', { de: 'Geografie', fr: 'Géographie' }),
        values: res.data?.geography?.values || [],
      }
    }
  } catch (err) {
    geoCache.value[code] = { label: tr('Geography', '地区', { de: 'Geografie', fr: 'Géographie' }), values: [] }
  }
}

async function onCountryChange() {
  selectedGeography.value = []
  if (selectedCode.value) await loadCountryDetail(selectedCode.value)
  emitValue()
}

function toggleGeography(v) {
  const i = selectedGeography.value.indexOf(v)
  if (i >= 0) selectedGeography.value.splice(i, 1)
  else selectedGeography.value.push(v)
  emitValue()
}

function emitValue() {
  if (!selectedCode.value) {
    emit('update:modelValue', { country: null, demographic_filters: null })
    return
  }
  const filters = selectedGeography.value.length > 0
    ? { geography_values: [...selectedGeography.value] }
    : null
  emit('update:modelValue', {
    country: selectedCode.value,
    demographic_filters: filters,
  })
}

// Keep the local code in sync when the parent resets the model.
watch(() => props.modelValue?.country, (next) => {
  if ((next || '') !== selectedCode.value) {
    selectedCode.value = next || ''
    if (selectedCode.value) loadCountryDetail(selectedCode.value)
  }
})
</script>

<style scoped>
.country-picker {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}
.cp-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.cp-label {
  font-size: 12px;
  color: var(--color-fg-muted, #9aa);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.cp-select {
  flex: 0 1 220px;
  background: linear-gradient(180deg, rgba(40,30,70,0.6) 0%, rgba(18,12,38,0.85) 100%);
  color: #f4f1ff;
  border: 1px solid rgba(167,139,250,0.28);
  border-radius: 9999px;
  padding: 6px 14px;
  font-size: 13px;
}
.cp-select:disabled { opacity: 0.6; cursor: not-allowed; }
.cp-geography { display: flex; flex-direction: column; gap: 6px; }
.cp-geo-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.cp-geo-label {
  font-size: 11px;
  color: var(--color-fg-muted, #9aa);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.cp-geo-clear {
  background: transparent;
  border: none;
  color: var(--color-accent, #76f);
  font-size: 11px;
  cursor: pointer;
}
.cp-geo-clear:disabled { opacity: 0.4; cursor: not-allowed; }
.cp-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  max-height: 160px;
  overflow-y: auto;
}
.cp-chip {
  background: var(--color-bg-2, #0e0f12);
  color: var(--color-fg, #d8dde6);
  border: 1px solid var(--color-border, #2a2d34);
  border-radius: 12px;
  padding: 2px 8px;
  font-size: 11px;
  cursor: pointer;
  transition: background 0.1s;
}
.cp-chip:hover:not(:disabled) { background: var(--color-bg-3, #15171b); }
.cp-chip.active {
  background: var(--color-accent, #76f);
  border-color: var(--color-accent, #76f);
  color: #fff;
}
.cp-chip:disabled { opacity: 0.5; cursor: not-allowed; }
.cp-hint, .cp-foot-hint {
  font-size: 10px;
  color: var(--color-fg-muted, #9aa);
  margin: 0;
  font-style: italic;
}
</style>
