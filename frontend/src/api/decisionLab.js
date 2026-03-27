import service, { requestWithRetry } from './index'

export function createLab(data) {
  return requestWithRetry(() =>
    service({ url: '/api/decision-lab/create', method: 'post', data })
  )
}

export function getLab(labId) {
  return service({ url: `/api/decision-lab/${labId}`, method: 'get' })
}

export function listLabs(limit = 50) {
  return service({ url: '/api/decision-lab/list', method: 'get', params: { limit } })
}

export function addBranch(labId, data) {
  return requestWithRetry(() =>
    service({ url: `/api/decision-lab/${labId}/branch`, method: 'post', data })
  )
}

export function removeBranch(labId, branchId) {
  return service({ url: `/api/decision-lab/${labId}/branch/${branchId}`, method: 'delete' })
}

export function prepareLab(labId) {
  return requestWithRetry(() =>
    service({ url: `/api/decision-lab/${labId}/prepare`, method: 'post' })
  )
}

export function runLab(labId, maxRounds = 72) {
  return requestWithRetry(() =>
    service({ url: `/api/decision-lab/${labId}/run`, method: 'post', data: { max_rounds: maxRounds } })
  )
}

export function getLabStatus(labId) {
  return service({ url: `/api/decision-lab/${labId}/status`, method: 'get' })
}

export function deleteLab(labId) {
  return service({ url: `/api/decision-lab/${labId}`, method: 'delete' })
}
