import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { compression } from 'vite-plugin-compression2'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendDir = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(frontendDir, '..')

/** Build Vite allowedHosts from Traefik DNS vars + optional extras. */
function parseAllowedHosts(env) {
  const hosts = new Set()
  const domain = (env.DOMAIN_NAME || '').trim()

  if (domain) {
    for (const sub of [env.SUBDOMAIN, env.API_SUBDOMAIN]) {
      const label = (sub || '').trim()
      if (label) hosts.add(`${label}.${domain}`)
    }
  }

  for (const raw of (env.VITE_DEV_ALLOWED_HOSTS || '').split(',')) {
    const host = raw.trim()
    if (host) hosts.add(host)
  }

  return [...hosts]
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Root .env (docker-compose env_file) + frontend/.env.local overrides
  const env = {
    ...loadEnv(mode, rootDir, ''),
    ...loadEnv(mode, frontendDir, ''),
    ...process.env,
  }

  const allowedHosts = parseAllowedHosts(env)
  const apiProxy = (env.VITE_DEV_API_PROXY || 'http://localhost:5001').replace(/\/$/, '')

  return {
    plugins: [
      vue(),
      compression({ algorithm: 'gzip' }),
      compression({ algorithm: 'brotliCompress' }),
    ],
    server: {
      port: Number(env.VITE_DEV_PORT) || 3000,
      open: env.VITE_DEV_OPEN !== 'false',
      host: true,
      ...(allowedHosts.length > 0 ? { allowedHosts } : {}),
      proxy: {
        '/api': {
          target: apiProxy,
          changeOrigin: true,
          secure: false,
        },
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return
            if (id.includes('/node_modules/d3')) return 'd3'
            if (/\/node_modules\/(vue|vue-router|@vue)\//.test(id)) return 'vue-vendor'
          },
        },
      },
    },
  }
})
