<script setup>
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  logs: { type: Array, default: () => [] }, // [{id?, level?, message}]
  height: { type: Number, default: 520 },
  filename: { type: String, default: 'logs.txt' },
  empty: { type: String, default: '等待执行日志...' }
})

const keyword = ref('')
const level = ref('all')
const follow = ref(true)
const wrap = ref(true)
const box = ref(null)
const MAX_RENDERED_LOGS = 2000

const LEVELS = [
  { value: 'all', label: '全部级别' },
  { value: 'info', label: '信息' },
  { value: 'warning', label: '警告' },
  { value: 'error', label: '错误' }
]

function lv(line) { return (line.level || 'info').toLowerCase() }

const filtered = computed(() => props.logs.filter(line => {
  if (level.value !== 'all' && lv(line) !== level.value) return false
  if (keyword.value && !(line.message || '').toLowerCase().includes(keyword.value.toLowerCase())) return false
  return true
}))
const rendered = computed(() => filtered.value.slice(-MAX_RENDERED_LOGS))
const hiddenCount = computed(() => Math.max(0, filtered.value.length - rendered.value.length))
const lineOffset = computed(() => filtered.value.length - rendered.value.length)

const errorCount = computed(() => props.logs.filter(x => lv(x) === 'error').length)
const warnCount = computed(() => props.logs.filter(x => lv(x) === 'warning').length)

function escapeHtml(text) {
  return String(text ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function escapeReg(text) { return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') }

function renderMessage(message) {
  const escaped = escapeHtml(message)
  if (!keyword.value) return escaped
  const reg = new RegExp(`(${escapeReg(escapeHtml(keyword.value))})`, 'gi')
  return escaped.replace(reg, '<mark>$1</mark>')
}

async function scrollBottom() {
  await nextTick()
  if (box.value && follow.value) box.value.scrollTop = box.value.scrollHeight
}
watch(() => props.logs.length, scrollBottom)
watch([keyword, level], () => { /* keep position on filter change */ })

function download() {
  const text = filtered.value.map(x => `[${(x.level || 'INFO').toUpperCase()}] ${x.message}`).join('\n')
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = props.filename
  link.click()
  URL.revokeObjectURL(link.href)
}
</script>

<template>
  <div class="log-console">
    <div class="log-toolbar">
      <el-input v-model="keyword" size="small" placeholder="搜索日志内容..." clearable class="log-search"/>
      <el-select v-model="level" size="small" class="log-level">
        <el-option v-for="item in LEVELS" :key="item.value" :label="item.label" :value="item.value"/>
      </el-select>
      <span class="log-count">
        {{ filtered.length }} / {{ logs.length }} 行
        <i v-if="warnCount" class="dot warn"/>{{ warnCount || '' }}
        <i v-if="errorCount" class="dot err"/>{{ errorCount || '' }}
      </span>
      <span class="spacer"/>
      <label class="switch"><input type="checkbox" v-model="follow"/><span>自动滚动</span></label>
      <label class="switch"><input type="checkbox" v-model="wrap"/><span>自动换行</span></label>
      <el-button size="small" :disabled="!filtered.length" @click="download">下载日志</el-button>
    </div>
    <div ref="box" class="log-body" :class="{ nowrap: !wrap }" :style="{ height: height + 'px' }">
      <div v-if="hiddenCount" class="log-limit">日志较多，实时窗口仅显示最近 {{ MAX_RENDERED_LOGS }} 行；下载日志仍包含全部内容</div>
      <div v-for="(line, i) in rendered" :key="line.id || i" class="log-line" :class="lv(line)">
        <span class="ln">{{ lineOffset + i + 1 }}</span><span class="msg" v-html="renderMessage(line.message)"/>
      </div>
      <div v-if="!filtered.length" class="log-empty">{{ logs.length ? '没有匹配当前条件的日志' : empty }}</div>
    </div>
  </div>
</template>

<style scoped>
.log-console { display: flex; flex-direction: column; gap: 10px; }
.log-toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.log-search { width: 240px; }
.log-level { width: 110px; }
.log-count { display: flex; align-items: center; gap: 5px; color: var(--text-muted); font-size: 12px; }
.log-count .dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.log-count .dot.warn { background: var(--warning); box-shadow: 0 0 6px var(--warning); }
.log-count .dot.err { background: var(--danger); box-shadow: 0 0 6px var(--danger); }
.spacer { flex: 1; }
.switch { display: flex; align-items: center; gap: 5px; color: var(--text-secondary); font-size: 12px; cursor: pointer; user-select: none; }
.switch input { accent-color: var(--primary); cursor: pointer; }
.log-body { overflow: auto; padding: 12px 0; border: 1px solid var(--border-color); border-radius: 10px; background: var(--console-bg); box-shadow: inset 0 0 30px rgba(0, 0, 0, .28); font: 13px/1.7 Consolas, "JetBrains Mono", monospace; }
.log-body.nowrap .msg { white-space: pre; }
.log-line { display: flex; padding: 0 14px; color: var(--console-text); }
.log-line:hover { background: rgba(255, 255, 255, .04); }
.log-line .ln { flex: 0 0 46px; padding-right: 12px; color: var(--text-muted); opacity: .55; text-align: right; user-select: none; }
.log-line .msg { flex: 1; white-space: pre-wrap; word-break: break-all; }
.log-line.error .msg { color: #ff8585; }
.log-line.warning .msg { color: #ffd278; }
.log-line.debug .msg { opacity: .62; }
.log-line :deep(mark) { padding: 0 1px; border-radius: 3px; color: #09131f; background: #ffd278; }
.log-limit { position: sticky; top: 0; z-index: 1; padding: 6px 14px; color: var(--warning); background: var(--console-bg); border-bottom: 1px solid var(--border-color); font-size: 12px; text-align: center; }
.log-empty { padding: 26px; color: var(--text-muted); text-align: center; }
</style>
