<script setup>
import { computed } from 'vue'

// segments: [{ key, label, count, tone: 'success'|'danger'|'warning'|'info'|'muted' }]
const props = defineProps({
  segments: { type: Array, default: () => [] },
  title: { type: String, default: '' }
})

const total = computed(() => props.segments.reduce((sum, x) => sum + (x.count || 0), 0))
const main = computed(() => props.segments.find(x => x.main) || props.segments[0])
const rate = computed(() => {
  if (!total.value || !main.value) return null
  return Math.round((main.value.count / total.value) * 1000) / 10
})
const TONES = {
  success: 'var(--success)', danger: 'var(--danger)', warning: 'var(--warning)',
  info: 'var(--primary)', accent: 'var(--accent)', muted: 'var(--text-muted)'
}
</script>

<template>
  <div class="stat-bar">
    <div class="stat-head">
      <span v-if="title" class="stat-title">{{ title }}</span>
      <span class="stat-total">共 {{ total }} 条</span>
      <span v-if="rate !== null" class="stat-rate" :style="{ color: TONES[main.tone || 'success'] }">{{ main.label }}率 {{ rate }}%</span>
    </div>
    <div class="bar">
      <div v-for="seg in segments.filter(x => x.count > 0)" :key="seg.key" class="seg"
           :style="{ width: (seg.count / total * 100) + '%', background: TONES[seg.tone || 'muted'] }"
           :title="`${seg.label}: ${seg.count}`"/>
      <div v-if="!total" class="seg empty" style="width:100%"/>
    </div>
    <div class="legend">
      <span v-for="seg in segments" :key="seg.key" class="item" :class="{ zero: !seg.count }">
        <i :style="{ background: TONES[seg.tone || 'muted'] }"/>{{ seg.label }} <b>{{ seg.count }}</b>
      </span>
    </div>
  </div>
</template>

<style scoped>
.stat-bar { display: flex; flex-direction: column; gap: 8px; }
.stat-head { display: flex; align-items: baseline; gap: 14px; }
.stat-title { color: var(--text-secondary); font-size: 13px; font-weight: 600; }
.stat-total { color: var(--text-muted); font-size: 12px; }
.stat-rate { margin-left: auto; font-size: 15px; font-weight: 800; }
.bar { display: flex; height: 8px; overflow: hidden; border-radius: 6px; background: var(--surface-soft); }
.seg { height: 100%; transition: width .4s ease; }
.seg.empty { background: var(--border-color); }
.legend { display: flex; flex-wrap: wrap; gap: 6px 18px; }
.legend .item { display: flex; align-items: center; gap: 6px; color: var(--text-secondary); font-size: 12px; }
.legend .item.zero { opacity: .45; }
.legend i { width: 8px; height: 8px; border-radius: 3px; display: inline-block; }
.legend b { color: var(--text-primary); font-size: 13px; }
</style>
