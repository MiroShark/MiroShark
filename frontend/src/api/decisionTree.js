import service from './index'

export const postTreeInit = (data) => {
  return service.post('/api/seed-chat/tree/init', data, { timeout: 60000 })
}

export const postTreeExpand = (data) => {
  return service.post('/api/seed-chat/tree/expand', data, { timeout: 90000 })
}

export const postTreeResearch = (data) => {
  return service.post('/api/seed-chat/tree/research', data, { timeout: 240000 })
}

export const postTreeUpdateNode = (data) => {
  return service.post('/api/seed-chat/tree/update-node', data, { timeout: 30000 })
}

export const postTreeSynthesize = (data) => {
  return service.post('/api/seed-chat/tree/synthesize', data, { timeout: 120000 })
}

export const postCompileForesight = (data) => {
  return service.post('/api/seed-chat/tree/compile-foresight', data, { timeout: 240000 })
}

export const postTreeScore = (data) => {
  return service.post('/api/seed-chat/tree/score', data, { timeout: 60000 })
}

export const postTreeAugmentBigPicture = (data) => {
  return service.post('/api/seed-chat/tree/augment-big-picture', data, { timeout: 30000 })
}

export const postTreeAugmentStoryDepth = (data) => {
  return service.post('/api/seed-chat/tree/augment-story-depth', data, { timeout: 30000 })
}
