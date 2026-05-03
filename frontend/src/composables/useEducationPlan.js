import { ref } from 'vue'
import { postEducationPlan } from '../api/education.js'

export function useEducationPlan({ sessionId, tree, infographicFormat, error }) {
  const educationPlan = ref(null)
  const educationInfographicPlan = ref(null)
  const educationOpen = ref(false)
  const planningEducation = ref(false)

  function loadEducationState(session) {
    if (session?.education_plan) educationPlan.value = session.education_plan
    if (session?.education_infographic_plan) educationInfographicPlan.value = session.education_infographic_plan
  }

  async function planEducation(force = false) {
    if (planningEducation.value) return
    if (educationPlan.value && !force) {
      educationOpen.value = true
      return
    }
    planningEducation.value = true
    error.value = ''
    try {
      const data = await postEducationPlan({
        session_id: sessionId,
        format: infographicFormat.value || 'tiktok',
      })
      if (data?.education_plan) educationPlan.value = data.education_plan
      if (data?.infographic_plan) educationInfographicPlan.value = data.infographic_plan
      educationOpen.value = true
    } catch (err) {
      error.value = err?.response?.data?.error || err.message
    } finally {
      planningEducation.value = false
    }
  }

  async function copyEducationJson() {
    if (!educationPlan.value) return
    try {
      await navigator.clipboard.writeText(JSON.stringify({ education_plan: educationPlan.value, infographic_plan: educationInfographicPlan.value }, null, 2))
    } catch {
      error.value = 'Copy failed — your browser blocked clipboard access.'
    }
  }

  function downloadEducationJson() {
    if (!educationPlan.value) return
    const date = new Date().toISOString().slice(0, 10)
    const slug = (tree.value?.question || 'education-plan')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60) || 'education-plan'
    const blob = new Blob([JSON.stringify({ education_plan: educationPlan.value, infographic_plan: educationInfographicPlan.value }, null, 2)], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `education-plan-${slug}-${date}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return {
    educationPlan,
    educationInfographicPlan,
    educationOpen,
    planningEducation,
    loadEducationState,
    planEducation,
    copyEducationJson,
    downloadEducationJson,
  }
}
