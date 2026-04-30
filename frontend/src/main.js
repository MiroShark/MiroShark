import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { i18nPlugin } from './i18n'

const app = createApp(App)

app.use(router)
app.use(i18nPlugin)

app.mount('#app')

// Register service worker for browser push notifications
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch((err) => {
    console.warn('[MiroShark] Service worker registration failed:', err)
  })
}
