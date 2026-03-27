/**
 * Temporarily store files, URLs, and requirements pending upload
 * Used for immediate redirect after clicking start engine on homepage, then making API calls on the Process page
 */
import { reactive } from 'vue'

const state = reactive({
  files: [],
  urls: '',
  simulationRequirement: '',
  isPending: false
})

export function setPendingUpload(files, requirement, urls = '') {
  state.files = files
  state.simulationRequirement = requirement
  state.urls = urls
  state.isPending = true
}

export function getPendingUpload() {
  return {
    files: state.files,
    urls: state.urls,
    simulationRequirement: state.simulationRequirement,
    isPending: state.isPending
  }
}

export function clearPendingUpload() {
  state.files = []
  state.urls = ''
  state.simulationRequirement = ''
  state.isPending = false
}

export default state
