import { ref, computed } from 'vue'

const STORAGE_KEY = 'miroshark.locale'
const ZH_WARNING_KEY = 'miroshark.zh-warning-seen'
const SUPPORTED = ['en', 'zh-CN']
const DEFAULT_LOCALE = 'en'

function readInitial() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && SUPPORTED.includes(saved)) return saved
  } catch (_) {}
  return DEFAULT_LOCALE
}

export const locale = ref(readInitial())

export const isZh = computed(() => locale.value === 'zh-CN')

export const showZhWarning = ref(false)

if (typeof document !== 'undefined') {
  document.documentElement.lang = locale.value
}

// If the user already had Chinese set before this feature shipped,
// silently mark the warning as seen so they don't get a surprise warning.
try {
  if (locale.value === 'zh-CN' && localStorage.getItem(ZH_WARNING_KEY) === null) {
    localStorage.setItem(ZH_WARNING_KEY, 'true')
  }
} catch (_) {}

export function setLocale(next) {
  if (!SUPPORTED.includes(next)) return
  const previous = locale.value
  locale.value = next
  try { localStorage.setItem(STORAGE_KEY, next) } catch (_) {}
  if (typeof document !== 'undefined') {
    document.documentElement.lang = next
  }
  // First-time switch from English to Chinese: surface the warning.
  if (next === 'zh-CN' && previous === 'en') {
    try {
      if (localStorage.getItem(ZH_WARNING_KEY) === null) {
        showZhWarning.value = true
      }
    } catch (_) {
      showZhWarning.value = true
    }
  }
}

export function dismissZhWarning() {
  showZhWarning.value = false
  try { localStorage.setItem(ZH_WARNING_KEY, 'true') } catch (_) {}
}

export function toggleLocale() {
  setLocale(locale.value === 'zh-CN' ? 'en' : 'zh-CN')
}

export function tr(en, zh) {
  if (locale.value === 'zh-CN' && zh != null && zh !== '') return zh
  return en
}

export function useI18n() {
  return {
    locale,
    isZh,
    setLocale,
    toggleLocale,
    tr,
    showZhWarning,
    dismissZhWarning,
  }
}

export const i18nPlugin = {
  install(app) {
    app.config.globalProperties.$tr = tr
    app.config.globalProperties.$isZh = () => locale.value === 'zh-CN'
    app.config.globalProperties.$setLocale = setLocale
    app.config.globalProperties.$toggleLocale = toggleLocale
    app.config.globalProperties.$showZhWarning = showZhWarning
    app.config.globalProperties.$dismissZhWarning = dismissZhWarning
  },
}

export const SUPPORTED_LOCALES = SUPPORTED
