import { computed, ref } from 'vue'
import { marked } from 'marked'
import { postCompileForesight } from '../api/decisionTree.js'

export function useForesightDocument({ sessionId, tree, error }) {
  const foresight = ref('')
  const foresightOpen = ref(false)
  const compilingForesight = ref(false)

  const renderedForesight = computed(() =>
    foresight.value ? marked.parse(foresight.value) : ''
  )

  function loadForesightState(session) {
    if (session?.foresight) foresight.value = session.foresight
  }

  async function compileForesight() {
    if (!tree.value || compilingForesight.value) return
    if (foresight.value && !foresightOpen.value) {
      foresightOpen.value = true
      return
    }
    compilingForesight.value = true
    error.value = ''
    try {
      const data = await postCompileForesight({ session_id: sessionId })
      if (data?.foresight) {
        foresight.value = data.foresight
        foresightOpen.value = true
      }
    } catch (err) {
      error.value = err?.response?.data?.error || err.message
    } finally {
      compilingForesight.value = false
    }
  }

  async function regenerateForesight() {
    if (compilingForesight.value) return
    compilingForesight.value = true
    error.value = ''
    try {
      const data = await postCompileForesight({ session_id: sessionId })
      if (data?.foresight) foresight.value = data.foresight
    } catch (err) {
      error.value = err?.response?.data?.error || err.message
    } finally {
      compilingForesight.value = false
    }
  }

  async function copyForesight() {
    try {
      await navigator.clipboard.writeText(foresight.value)
    } catch {
      error.value = 'Copy failed — your browser blocked clipboard access.'
    }
  }

  function downloadForesight() {
    if (!foresight.value) return
    const date = new Date().toISOString().slice(0, 10)
    const slug = (tree.value?.question || 'foresight')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60) || 'foresight'
    const blob = new Blob([foresight.value], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `foresight-${slug}-${date}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return {
    foresight,
    foresightOpen,
    compilingForesight,
    renderedForesight,
    loadForesightState,
    compileForesight,
    regenerateForesight,
    copyForesight,
    downloadForesight,
  }
}
