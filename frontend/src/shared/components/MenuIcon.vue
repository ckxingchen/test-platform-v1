<script setup>
const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 18 }
})
// Linear icon 风格：24x24 viewBox，1.6 描边，自动继承 currentColor
const paths = {
  dashboard: 'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z',
  folder: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v1H3V7zm0 3h18v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-8z',
  server: 'M4 4h16a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zm0 10h16a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1zM7 7h.01M7 17h.01',
  tasks: 'M9 5h11a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zm0 14h11a1 1 0 0 1 1 1v0a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1v0a1 1 0 0 1 1-1zM4 7h.01M4 11h.01M4 15h.01M4 19h.01',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-7 8a7 7 0 0 1 14 0z',
  robot: 'M12 2a1 1 0 0 1 1 1v1h3a2 2 0 0 1 2 2v3a2 2 0 0 1-1 1.73V17a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2v-6.27A2 2 0 0 1 6 9V6a2 2 0 0 1 2-2h3V3a1 1 0 0 1 1-1zm-2 7a1 1 0 1 0 0 2 1 1 0 0 0 0-2zm4 0a1 1 0 1 0 0 2 1 1 0 0 0 0-2zM3 13a1 1 0 0 1 2 0v6a1 1 0 0 1-2 0v-6zm16 0a1 1 0 0 1 2 0v6a1 1 0 0 1-2 0v-6zM9 19h6v1H9z',
  cube: 'M12 2 3 7v10l9 5 9-5V7l-9-5zm0 2.18L18.82 8 12 11.82 5.18 8 12 4.18zM5 9.31l6 3.38v7.06l-6-3.33v-7.11zm14 0v7.11l-6 3.33v-7.06l6-3.38z',
  briefcase: 'M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2h4a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h4zm2 0h4V4h-4v2z',
  play: 'M8 5v14l11-7z',
  list: 'M4 6h16M4 12h16M4 18h16',
  default: 'M5 4h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z'
}
const d = () => paths[props.name] || paths.default
</script>

<template>
  <svg class="menu-icon" :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path :d="d()"/>
  </svg>
</template>

<style scoped>
.menu-icon { flex: none; display: inline-block; vertical-align: middle; }
</style>
