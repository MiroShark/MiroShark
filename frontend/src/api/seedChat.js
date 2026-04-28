import service, { requestWithRetry } from './index'

/**
 * Post a turn in the seed chat conversation
 * @param {Object} data - { messages, seed_state }
 */
export const postTurn = (data) => {
  return requestWithRetry(() => service.post('/api/seed-chat/turn', data), 3, 1000)
}

/**
 * Launch a new seed chat session
 * @param {Object} data - { seed }
 */
export const postLaunch = (data) => {
  return requestWithRetry(() => service.post('/api/seed-chat/launch', data), 3, 1000)
}
