<template>
  <router-view />
  <Toast ref="toastComponent" />
</template>

<script setup>
import { ref, onMounted } from 'vue'
import Toast from './components/Toast.vue'
import { setToastRef } from './composables/useToast'

const toastComponent = ref(null)
onMounted(() => setToastRef(toastComponent.value))
</script>

<style>
/* Global style reset */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body, #app {
  font-family: 'Inter', 'Space Grotesk', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #000000;
  background-color: #ffffff;
}

/* Scrollbar styles */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
}

::-webkit-scrollbar-thumb {
  background: #000000;
}

::-webkit-scrollbar-thumb:hover {
  background: #333333;
}

/* Global button styles */
button {
  font-family: inherit;
}
</style>
