import service from './index'

export const postInfographicNarrationPlan = (data) => {
  return service.post('/api/seed-chat/tree/infographics/narration/plan', data, { timeout: 60000 })
}

export const postRenderInfographicAudio = (data) => {
  return service.post('/api/seed-chat/tree/infographics/audio/render', data, { timeout: 300000 })
}
