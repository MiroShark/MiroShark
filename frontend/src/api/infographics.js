import service from './index'

export const postInfographicPlan = (data) => {
  return service.post('/api/seed-chat/tree/infographics/plan', data, { timeout: 60000 })
}

export const postRenderInfographic = (data) => {
  return service.post('/api/seed-chat/tree/infographics/render', data, { timeout: 240000 })
}

export const getInfographicAccounting = (sessionId) => {
  return service.get('/api/seed-chat/tree/infographics/accounting', { params: { session_id: sessionId } })
}
