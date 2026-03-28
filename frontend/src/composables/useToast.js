import { ref } from 'vue'

const toastRef = ref(null)

export function setToastRef(ref) {
  toastRef.value = ref
}

export function useToast() {
  return {
    error: (msg) => toastRef.value?.add(msg, 'error'),
    success: (msg) => toastRef.value?.add(msg, 'success'),
    warning: (msg) => toastRef.value?.add(msg, 'warning'),
    info: (msg) => toastRef.value?.add(msg, 'info'),
  }
}
