import { ref, computed } from 'vue'

const STORAGE_KEY = 'miroshark.locale'
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

if (typeof document !== 'undefined') {
  document.documentElement.lang = locale.value
}

export function setLocale(next) {
  if (!SUPPORTED.includes(next)) return
  locale.value = next
  try { localStorage.setItem(STORAGE_KEY, next) } catch (_) {}
  if (typeof document !== 'undefined') {
    document.documentElement.lang = next
  }
}

export function toggleLocale() {
  setLocale(locale.value === 'zh-CN' ? 'en' : 'zh-CN')
}

export function tr(en, zh) {
  if (locale.value === 'zh-CN' && zh != null && zh !== '') return zh
  return en
}

export function useI18n() {
  return { locale, isZh, setLocale, toggleLocale, tr }
}

export const i18nPlugin = {
  install(app) {
    app.config.globalProperties.$tr = tr
    app.config.globalProperties.$isZh = () => locale.value === 'zh-CN'
    app.config.globalProperties.$setLocale = setLocale
    app.config.globalProperties.$toggleLocale = toggleLocale
  },
}

export const SUPPORTED_LOCALES = SUPPORTED
