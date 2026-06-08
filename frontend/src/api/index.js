import axios from 'axios'
import { locale } from '../i18n'

// Default to same-origin `/api` so Vite's dev proxy works when the UI is
// opened via gpu.local / LAN hostnames. Set VITE_API_BASE_URL for production
// (e.g. https://api.example.com) or direct backend access on the same machine.
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 300000, // 5-minute timeout (ontology generation may take a long time)
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor — forwards the active UI locale so the backend can
// localise template metadata, error messages, and feed copy.
service.interceptors.request.use(
  config => {
    if (locale && locale.value) {
      config.headers = config.headers || {}
      config.headers['X-MiroShark-Locale'] = locale.value
      config.headers['Accept-Language'] = locale.value
    }
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor (fault-tolerant retry mechanism)
service.interceptors.response.use(
  response => {
    const res = response.data
    
    // If the returned status is not success, throw an error
    if (!res.success && res.success !== undefined) {
      console.error('API Error:', res.error || res.message || 'Unknown error')
      return Promise.reject(new Error(res.error || res.message || 'Error'))
    }
    
    return res
  },
  error => {
    const body = error.response?.data
    const apiMessage =
      (typeof body === 'object' && body && (body.error || body.message)) ||
      null
    if (apiMessage) {
      console.error('Response error:', apiMessage)
      return Promise.reject(new Error(apiMessage))
    }

    console.error('Response error:', error)

    // Handle timeout
    if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
      console.error('Request timeout')
    }

    // Handle network error
    if (error.message === 'Network Error') {
      console.error('Network error - please check your connection')
    }

    return Promise.reject(error)
  }
)

// Request function with retry
export const requestWithRetry = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      if (i === maxRetries - 1) throw error
      
      console.warn(`Request failed, retrying (${i + 1}/${maxRetries})...`)
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}

export default service
