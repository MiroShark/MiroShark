import { computed, ref } from 'vue'
import {
  postInfographicPlan,
  postRenderInfographic,
  getInfographicAccounting,
} from '../api/infographics.js'
import {
  postInfographicNarrationPlan,
  postRenderInfographicAudio,
} from '../api/narration.js'

export function useInfographicTimeline({ sessionId, route, router, tree, error }) {
  const infographicPlan = ref(null)
  const infographicOpen = ref(false)
  const planningInfographics = ref(false)
  const selectedInfographicIndex = ref(0)
  const infographicRenders = ref({})
  const renderingInfographic = ref(false)
  const batchRenderingInfographics = ref(false)
  const batchRenderProgress = ref({ current: 0, total: 0, label: '' })
  const batchRenderError = ref('')
  const infographicFormat = ref('landscape')
  const infographicAccounting = ref(null)
  const narrationScript = ref(null)
  const audioRender = ref(null)
  const slideAudioRenders = ref({})
  const planningNarration = ref(false)
  const renderingNarration = ref(false)
  const timelinePlayerOpen = ref(false)
  const playerIndex = ref(0)
  const playerPlaying = ref(false)
  const playerAutoAdvance = ref(true)
  const timelinePlayerRef = ref(null)
  const generatingAllSlideClips = ref(false)
  const clipGenerationProgress = ref({ current: 0, total: 0, label: '' })
  const clipGenerationError = ref('')

  const selectedInfographicSlide = computed(() =>
    infographicPlan.value?.sequence?.[selectedInfographicIndex.value] || null
  )

  function shouldOpenInfographicsOnLoad() {
    return route.query.infographics === '1'
  }

  function loadInfographicState(session) {
    if (session?.infographic_plan) {
      infographicPlan.value = session.infographic_plan
      infographicOpen.value = shouldOpenInfographicsOnLoad()
    }
    if (session?.infographic_renders) {
      infographicRenders.value = session.infographic_renders
    }
    if (session?.narration_script) {
      narrationScript.value = session.narration_script
    }
    if (session?.audio_renders?.narration) {
      audioRender.value = session.audio_renders.narration
    }
    if (session?.audio_renders?.slides) {
      slideAudioRenders.value = session.audio_renders.slides
    }
  }

  function clearInfographicArtifacts() {
    infographicPlan.value = null
    infographicRenders.value = {}
    narrationScript.value = null
    audioRender.value = null
    slideAudioRenders.value = {}
  }

  function slideKeyForIndex(index) {
    const slide = infographicPlan.value?.sequence?.[index]
    return slide?.slide_id || String(index)
  }

  function renderForIndex(index) {
    const key = slideKeyForIndex(index)
    const stable = infographicRenders.value?.[key]
    if (stable) return stable
    const legacy = infographicRenders.value?.[String(index)]
    if (!legacy) return null
    if (legacy.slide_id && legacy.slide_id !== key) return null
    return legacy
  }

  function audioForIndex(index) {
    const key = slideKeyForIndex(index)
    const stable = slideAudioRenders.value?.[key]
    if (stable) return stable
    const legacy = slideAudioRenders.value?.[String(index)]
    if (!legacy) return null
    if (legacy.slide_id && legacy.slide_id !== key) return null
    return legacy
  }

  function hasInfographicRender(index) {
    return !!renderForIndex(index)
  }

  const currentInfographicRender = computed(() =>
    renderForIndex(selectedInfographicIndex.value)
  )

  function narrationBeatFor(index) {
    const key = slideKeyForIndex(index)
    return narrationScript.value?.slides?.find((beat) => beat.slide_id === key || beat.slide_index === index) || null
  }

  const selectedNarrationBeat = computed(() => narrationBeatFor(selectedInfographicIndex.value))
  const currentSlideAudioRender = computed(() => audioForIndex(selectedInfographicIndex.value))
  const nextUnrenderedSlides = computed(() => {
    const sequence = infographicPlan.value?.sequence || []
    return sequence
      .map((slide, index) => ({ slide, index, key: slide.slide_id || String(index) }))
      .filter(row => !renderForIndex(row.index))
      .slice(0, Math.max(0, Math.min(5, infographicAccounting.value?.openai_remaining_today ?? 5)))
  })

  function timelineDepthFor(slide) {
    return {
      depth: Number.isInteger(slide?.depth) ? slide.depth : 0,
      chapter: slide?.chapter || 'Story beat',
      parent: slide?.parent || '',
      parentSlideIndex: Number.isInteger(slide?.parent_slide_index) ? slide.parent_slide_index : null,
    }
  }

  const timelineRows = computed(() =>
    (infographicPlan.value?.sequence || []).map((slide, index) => ({
      slide,
      index,
      slideKey: slide.slide_id || String(index),
      ...timelineDepthFor(slide),
    }))
  )

  const playerSlide = computed(() => infographicPlan.value?.sequence?.[playerIndex.value] || null)
  const playerRender = computed(() => renderForIndex(playerIndex.value))
  const playerAudio = computed(() => audioForIndex(playerIndex.value))
  const playerBeat = computed(() => narrationBeatFor(playerIndex.value))

  async function planInfographics() {
    if (!tree.value || planningInfographics.value) return
    if (infographicPlan.value && !infographicOpen.value) {
      infographicOpen.value = true
      router.replace({ name: 'DecisionTree', params: { sessionId }, query: { ...route.query, infographics: '1' } })
      return
    }
    await regenerateInfographics()
  }

  async function regenerateInfographics() {
    if (!tree.value || planningInfographics.value) return
    planningInfographics.value = true
    error.value = ''
    try {
      const data = await postInfographicPlan({ session_id: sessionId })
      if (data?.infographic_plan) {
        infographicPlan.value = data.infographic_plan
        infographicRenders.value = {}
        narrationScript.value = null
        audioRender.value = null
        slideAudioRenders.value = {}
        await refreshInfographicAccounting()
        selectedInfographicIndex.value = 0
        infographicOpen.value = true
        router.replace({ name: 'DecisionTree', params: { sessionId }, query: { ...route.query, infographics: '1' } })
      }
    } catch (err) {
      error.value = err?.response?.data?.error || err.message
    } finally {
      planningInfographics.value = false
    }
  }

  async function refreshInfographicAccounting() {
    try {
      const data = await getInfographicAccounting(sessionId)
      if (data?.render_accounting) infographicAccounting.value = data.render_accounting
    } catch {
      // Non-critical; rendering endpoint still enforces limits server-side.
    }
  }

  function setInfographicFormat(format) {
    if (infographicFormat.value === format) return
    infographicFormat.value = format
    clearInfographicArtifacts()
    regenerateInfographics()
  }

  async function renderSelectedInfographic() {
    if (!infographicPlan.value || renderingInfographic.value || batchRenderingInfographics.value) return
    renderingInfographic.value = true
    error.value = ''
    batchRenderError.value = ''
    try {
      const data = await renderInfographicAtIndex(selectedInfographicIndex.value)
      if (data?.render) {
        storeInfographicRender(selectedInfographicIndex.value, data)
        if (data.render_accounting) infographicAccounting.value = data.render_accounting
      }
    } catch (err) {
      error.value = err?.response?.data?.error || err.message
    } finally {
      renderingInfographic.value = false
    }
  }

  async function renderInfographicAtIndex(index) {
    return postRenderInfographic({
      session_id: sessionId,
      slide_index: index,
      slide_id: slideKeyForIndex(index),
      provider: 'openai',
      render_mode: 'strict',
      model: 'gpt-image-2',
      aspect_ratio: infographicPlan.value?.aspect_ratio || (infographicFormat.value === 'tiktok' ? '9:16' : '16:9'),
      image_size: '1K',
    })
  }

  function storeInfographicRender(index, data) {
    if (!data?.render) return
    infographicRenders.value = {
      ...infographicRenders.value,
      [data.slide_id || data.render.slide_id || slideKeyForIndex(index)]: data.render,
    }
  }

  async function renderNextInfographics() {
    if (!infographicPlan.value || batchRenderingInfographics.value || renderingInfographic.value) return
    const targets = nextUnrenderedSlides.value
    if (!targets.length) return
    batchRenderingInfographics.value = true
    batchRenderError.value = ''
    error.value = ''
    batchRenderProgress.value = { current: 0, total: targets.length, label: 'Starting…' }
    try {
      for (let i = 0; i < targets.length; i += 1) {
        const target = targets[i]
        batchRenderProgress.value = { current: i + 1, total: targets.length, label: `Rendering slide ${target.index + 1}: ${target.slide.title}` }
        try {
          const data = await renderInfographicAtIndex(target.index)
          storeInfographicRender(target.index, data)
          if (data?.render_accounting) infographicAccounting.value = data.render_accounting
        } catch (err) {
          const msg = clipErrorMessage(err)
          batchRenderError.value = `Stopped at slide ${target.index + 1}: ${msg}`
          break
        }
      }
    } finally {
      batchRenderingInfographics.value = false
    }
  }

  function openTimelinePlayer() {
    if (!infographicPlan.value?.sequence?.length) return
    playerIndex.value = selectedInfographicIndex.value || 0
    playerPlaying.value = false
    timelinePlayerOpen.value = true
  }

  function closeTimelinePlayer() {
    if (timelinePlayerRef.value?.audioRef) timelinePlayerRef.value.audioRef.pause()
    playerPlaying.value = false
    timelinePlayerOpen.value = false
  }

  function previousPlayerSlide() {
    if (playerIndex.value <= 0) return
    playerIndex.value -= 1
    playerPlaying.value = false
  }

  function nextPlayerSlide() {
    const total = infographicPlan.value?.sequence?.length || 0
    if (playerIndex.value >= total - 1) return
    playerIndex.value += 1
    playerPlaying.value = false
  }

  async function playCurrentSlide() {
    const audio = timelinePlayerRef.value?.audioRef
    if (!audio || !playerAudio.value) return
    try {
      audio.currentTime = 0
      await audio.play()
      playerPlaying.value = true
    } catch {
      error.value = 'Audio playback was blocked by the browser. Press play on the audio control.'
    }
  }

  function onPlayerAudioEnded() {
    playerPlaying.value = false
    if (playerAutoAdvance.value) {
      const total = infographicPlan.value?.sequence?.length || 0
      if (playerIndex.value < total - 1) {
        playerIndex.value += 1
        setTimeout(() => playCurrentSlide(), 150)
      }
    }
  }

  async function planNarration() {
    if (!infographicPlan.value || planningNarration.value) return
    planningNarration.value = true
    error.value = ''
    clipGenerationError.value = ''
    try {
      const data = await postInfographicNarrationPlan({
        session_id: sessionId,
        format: infographicFormat.value,
        target_seconds: infographicFormat.value === 'tiktok' ? 75 : 90,
      })
      if (data?.narration_script) {
        narrationScript.value = data.narration_script
        audioRender.value = null
      }
    } catch (err) {
      error.value = err?.response?.data?.error || err.message
    } finally {
      planningNarration.value = false
    }
  }

  async function renderNarrationAudio() {
    if (!infographicPlan.value || !narrationScript.value || renderingNarration.value) return
    renderingNarration.value = true
    error.value = ''
    clipGenerationError.value = ''
    try {
      const data = await postRenderInfographicAudio({
        session_id: sessionId,
        format: infographicFormat.value,
        slide_index: selectedInfographicIndex.value,
        slide_id: slideKeyForIndex(selectedInfographicIndex.value),
      })
      if (data?.narration_script) narrationScript.value = data.narration_script
      if (data?.audio_render) {
        slideAudioRenders.value = {
          ...slideAudioRenders.value,
          [data.audio_render.slide_id || slideKeyForIndex(selectedInfographicIndex.value)]: data.audio_render,
        }
      }
    } catch (err) {
      error.value = err?.response?.data?.error || err.message
    } finally {
      renderingNarration.value = false
    }
  }

  function clipErrorMessage(err) {
    return err?.response?.data?.error || err.message || String(err)
  }

  async function generateAllSlideClips() {
    if (!narrationScript.value?.slides?.length || generatingAllSlideClips.value) return
    generatingAllSlideClips.value = true
    clipGenerationError.value = ''
    error.value = ''
    const beats = narrationScript.value.slides
    clipGenerationProgress.value = { current: 0, total: beats.length, label: 'Starting…' }
    try {
      for (let i = 0; i < beats.length; i += 1) {
        const beat = beats[i]
        const key = beat.slide_id || String(beat.slide_index)
        if (slideAudioRenders.value?.[key]) {
          clipGenerationProgress.value = { current: i + 1, total: beats.length, label: `Slide ${beat.slide_index + 1} already exists` }
          continue
        }
        clipGenerationProgress.value = { current: i + 1, total: beats.length, label: `Generating slide ${beat.slide_index + 1}…` }
        try {
          const data = await postRenderInfographicAudio({
            session_id: sessionId,
            format: infographicFormat.value,
            slide_index: beat.slide_index,
            slide_id: beat.slide_id,
            provider: 'local_piper',
          })
          if (data?.narration_script) narrationScript.value = data.narration_script
          if (data?.audio_render) {
            slideAudioRenders.value = {
              ...slideAudioRenders.value,
              [key]: data.audio_render,
            }
          }
        } catch (err) {
          const msg = clipErrorMessage(err)
          clipGenerationError.value = `Stopped at slide ${beat.slide_index + 1}: ${msg}`
          break
        }
      }
    } finally {
      generatingAllSlideClips.value = false
      const done = Object.keys(slideAudioRenders.value || {}).length
      clipGenerationProgress.value = {
        current: Math.min(done, beats.length),
        total: beats.length,
        label: clipGenerationError.value ? 'Paused — retry later' : 'Complete',
      }
    }
  }

  async function copyNarrationScript() {
    if (!narrationScript.value?.full_voiceover) return
    try {
      await navigator.clipboard.writeText(narrationScript.value.full_voiceover)
    } catch {
      error.value = 'Copy failed — your browser blocked clipboard access.'
    }
  }

  async function copyInfographicPrompt() {
    if (!selectedInfographicSlide.value?.image_prompt) return
    try {
      await navigator.clipboard.writeText(selectedInfographicSlide.value.image_prompt)
    } catch {
      error.value = 'Copy failed — your browser blocked clipboard access.'
    }
  }

  async function copyInfographicJson() {
    if (!infographicPlan.value) return
    try {
      await navigator.clipboard.writeText(JSON.stringify(infographicPlan.value, null, 2))
    } catch {
      error.value = 'Copy failed — your browser blocked clipboard access.'
    }
  }

  function downloadInfographicJson() {
    if (!infographicPlan.value) return
    const date = new Date().toISOString().slice(0, 10)
    const slug = (tree.value?.question || 'infographics')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60) || 'infographics'
    const blob = new Blob([JSON.stringify(infographicPlan.value, null, 2)], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `infographic-plan-${slug}-${date}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return {
    infographicPlan,
    infographicOpen,
    planningInfographics,
    selectedInfographicIndex,
    infographicRenders,
    renderingInfographic,
    batchRenderingInfographics,
    batchRenderProgress,
    batchRenderError,
    infographicFormat,
    infographicAccounting,
    narrationScript,
    audioRender,
    slideAudioRenders,
    planningNarration,
    renderingNarration,
    timelinePlayerOpen,
    playerIndex,
    playerPlaying,
    playerAutoAdvance,
    timelinePlayerRef,
    generatingAllSlideClips,
    clipGenerationProgress,
    clipGenerationError,
    selectedInfographicSlide,
    currentInfographicRender,
    selectedNarrationBeat,
    currentSlideAudioRender,
    nextUnrenderedSlides,
    timelineRows,
    playerSlide,
    playerRender,
    playerAudio,
    playerBeat,
    loadInfographicState,
    clearInfographicArtifacts,
    slideKeyForIndex,
    renderForIndex,
    audioForIndex,
    hasInfographicRender,
    narrationBeatFor,
    planInfographics,
    regenerateInfographics,
    refreshInfographicAccounting,
    setInfographicFormat,
    renderSelectedInfographic,
    renderNextInfographics,
    openTimelinePlayer,
    closeTimelinePlayer,
    previousPlayerSlide,
    nextPlayerSlide,
    playCurrentSlide,
    onPlayerAudioEnded,
    planNarration,
    renderNarrationAudio,
    generateAllSlideClips,
    copyNarrationScript,
    copyInfographicPrompt,
    copyInfographicJson,
    downloadInfographicJson,
  }
}
