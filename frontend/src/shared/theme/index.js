import { computed, ref } from 'vue'

const STORAGE_KEY = 'kw-platform-theme'
const theme = ref('dark')
let initialized = false

function preferredTheme() {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'light' || saved === 'dark') return saved
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function setTheme(value, persist = true) {
  const next = value === 'light' ? 'light' : 'dark'
  theme.value = next
  document.documentElement.dataset.theme = next
  document.documentElement.style.colorScheme = next
  if (persist) localStorage.setItem(STORAGE_KEY, next)
}

export function toggleTheme() {
  setTheme(theme.value === 'dark' ? 'light' : 'dark')
}

export function initTheme() {
  if (initialized) return
  initialized = true
  setTheme(preferredTheme(), false)
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  media.addEventListener('change', event => {
    if (!localStorage.getItem(STORAGE_KEY)) setTheme(event.matches ? 'dark' : 'light', false)
  })
}

export function useTheme() {
  return {
    isDark: computed(() => theme.value === 'dark'),
    toggleTheme
  }
}
