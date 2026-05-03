import service from './index'

export const postEducationPlan = (data) => {
  return service.post('/api/seed-chat/education/plan', data, { timeout: 60000 })
}
