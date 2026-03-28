import service, { requestWithRetry } from './index'

/**
 * Generate ontology (upload documents and simulation requirements)
 * @param {Object} data - Contains files, simulation_requirement, project_name, etc.
 * @returns {Promise}
 */
export function generateOntology(formData) {
  return requestWithRetry(() => 
    service({
      url: '/api/graph/ontology/generate',
      method: 'post',
      data: formData,
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  )
}

/**
 * Build knowledge graph
 * @param {Object} data - Contains project_id, graph_name, etc.
 * @returns {Promise}
 */
export function buildGraph(data) {
  return requestWithRetry(() =>
    service({
      url: '/api/graph/build',
      method: 'post',
      data
    })
  )
}

/**
 * Query task status
 * @param {String} taskId - Task ID
 * @returns {Promise}
 */
export function getTaskStatus(taskId) {
  return service({
    url: `/api/graph/task/${taskId}`,
    method: 'get'
  })
}

/**
 * Get graph data
 * @param {String} graphId - Graph ID
 * @returns {Promise}
 */
export function getGraphData(graphId) {
  return service({
    url: `/api/graph/data/${graphId}`,
    method: 'get'
  })
}

/**
 * Get project information
 * @param {String} projectId - Project ID
 * @returns {Promise}
 */
export function getProject(projectId) {
  return service({
    url: `/api/graph/project/${projectId}`,
    method: 'get'
  })
}

/**
 * Research a topic — LLM generates search queries, fetches web sources
 * @param {String} topic - Topic to research
 * @param {Number} maxSources - Max sources to fetch (default 10)
 * @param {String} intent - Optional intent for gap-guided research
 * @returns {Promise}
 */
/**
 * Suggest a simulation requirement based on topic and intent
 */
export function suggestRequirement(topic, intent = '', urls = '') {
  return requestWithRetry(() =>
    service({
      url: '/api/graph/suggest-requirement',
      method: 'post',
      data: { topic, intent, urls }
    })
  )
}

export function researchTopic(topic, maxSources = 10, intent = '') {
  const data = { topic, max_sources: maxSources }
  if (intent) data.intent = intent
  return requestWithRetry(() =>
    service({
      url: '/api/graph/research',
      method: 'post',
      data
    })
  )
}
