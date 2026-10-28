<script setup>
import { useTheme } from './index'

defineProps({ compact: { type: Boolean, default: false } })
const { isDark, toggleTheme } = useTheme()
</script>

<template>
  <button class="theme-toggle" :class="{ compact }" type="button" :aria-label="isDark ? '切换到浅色主题' : '切换到深色主题'" :title="isDark ? '切换到浅色主题' : '切换到深色主题'" @click="toggleTheme">
    <span class="toggle-track"><span class="toggle-orbit"/><span class="toggle-core" :class="{ moon: isDark }"/></span>
    <span v-if="!compact" class="toggle-label">{{ isDark ? '深色' : '浅色' }}</span>
  </button>
</template>

<style scoped>
.theme-toggle{height:38px;display:inline-flex;align-items:center;gap:9px;padding:0 12px;border:1px solid var(--border-color);border-radius:12px;background:var(--surface-soft);color:var(--text-secondary);cursor:pointer;transition:.25s ease;font:inherit}.theme-toggle:hover{color:var(--text-primary);border-color:var(--primary);box-shadow:0 0 20px var(--primary-glow)}.theme-toggle.compact{width:38px;padding:0;justify-content:center;border-radius:10px}.toggle-track{position:relative;width:21px;height:21px;display:grid;place-items:center}.toggle-orbit{position:absolute;inset:1px;border:1px dashed var(--primary);border-radius:50%;animation:theme-orbit 8s linear infinite}.toggle-core{width:9px;height:9px;border-radius:50%;background:#f8c85a;box-shadow:0 0 10px #f8c85a;transition:.3s ease}.toggle-core.moon{background:#8fe7ff;box-shadow:0 0 10px var(--primary);transform:translateX(2px)}.toggle-core.moon::after{content:"";display:block;width:8px;height:8px;border-radius:50%;background:var(--surface-soft);transform:translate(3px,-2px)}.toggle-label{font-size:12px;font-weight:600;letter-spacing:.08em}@keyframes theme-orbit{to{transform:rotate(360deg)}}@media (prefers-reduced-motion:reduce){.toggle-orbit{animation:none}}
</style>
