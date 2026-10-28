<script setup>
import { computed, ref } from 'vue'

// 零依赖语法高亮编辑器：透明 textarea 叠加在高亮 pre 之上，滚动同步。
const props = defineProps({
  modelValue: { type: String, default: '' },
  language: { type: String, default: 'text' }, // ini | yaml | json | python | text
  height: { type: Number, default: 460 },
  readonly: { type: Boolean, default: false },
  placeholder: { type: String, default: '' }
})
const emit = defineEmits(['update:modelValue'])

const area = ref(null)
const back = ref(null)
const gutter = ref(null)

const PY_KEYWORDS = new Set(('False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield').split(' '))

function esc(text) { return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') }
function span(type, text) { return `<span class="tok-${type}">${esc(text)}</span>` }

function tokenizeIni(line) {
  if (/^\s*[;#]/.test(line)) return span('comment', line)
  const section = line.match(/^(\s*)(\[.*\])(\s*)$/)
  if (section) return esc(section[1]) + span('section', section[2]) + esc(section[3])
  const kv = line.match(/^(\s*[^=;#\s][^=]*)(\s*=\s*)(.*)$/)
  if (kv) return span('key', kv[1]) + span('punct', kv[2]) + span('value', kv[3])
  return esc(line)
}

function tokenizeYaml(line) {
  const commentAt = line.search(/(^|\s)#/)
  let body = line, comment = ''
  if (commentAt >= 0 && !/^\s*["']/.test(line)) {
    body = line.slice(0, commentAt)
    comment = line.slice(commentAt)
  }
  let html = ''
  const kv = body.match(/^(\s*(?:-\s+)?)([^:"'][^:]*)(:)(\s*)(.*)$/)
  if (kv) {
    html = esc(kv[1]) + span('key', kv[2]) + span('punct', kv[3]) + esc(kv[4]) + colorScalar(kv[5])
  } else {
    html = colorScalar(body)
  }
  return html + (comment ? span('comment', comment) : '')
}

function colorScalar(text) {
  if (!text) return ''
  const t = text.trim()
  if (/^(['"]).*\1$/.test(t)) {
    const lead = text.slice(0, text.indexOf(t))
    return esc(lead) + span('string', t)
  }
  if (/^(true|false|yes|no|on|off|null|~)$/i.test(t)) return span('keyword', text)
  if (/^-?\d+(\.\d+)?$/.test(t)) return span('number', text)
  return esc(text)
}

function tokenizeJson(line) {
  let html = '', rest = line, m
  const reg = /("(?:\\.|[^"\\])*")(\s*:)?/g
  let last = 0
  while ((m = reg.exec(line))) {
    html += colorJsonPlain(line.slice(last, m.index))
    html += m[2] ? span('key', m[1]) + span('punct', m[2]) : span('string', m[1])
    last = m.index + m[0].length
  }
  html += colorJsonPlain(line.slice(last))
  return html
}
function colorJsonPlain(text) {
  return esc(text).replace(/\b(true|false|null)\b/g, '<span class="tok-keyword">$1</span>')
    .replace(/(-?\d+(\.\d+)?([eE][+-]?\d+)?)/g, '<span class="tok-number">$1</span>')
}

function tokenizePython(line) {
  const hashAt = line.indexOf('#')
  const inStr = line.slice(0, Math.max(hashAt, 0))
  const hasStr = /['"]/.test(inStr)
  let body = line, comment = ''
  if (hashAt >= 0 && !hasStr) { body = line.slice(0, hashAt); comment = line.slice(hashAt) }
  let html = esc(body)
    .replace(/(&quot;.*?&quot;|&#039;.*?&#039;)/g, '<span class="tok-string">$1</span>')
    .replace(/\b([A-Za-z_]\w*)\b/g, w => PY_KEYWORDS.has(w) ? `<span class="tok-keyword">${w}</span>` : w)
    .replace(/\b(\d+(\.\d+)?)\b/g, '<span class="tok-number">$1</span>')
  if (/^\s*@/.test(body)) html = span('section', body)
  return html + (comment ? span('comment', comment) : '')
}

function renderLine(line) {
  switch (props.language) {
    case 'ini': return tokenizeIni(line)
    case 'yaml': case 'yml': return tokenizeYaml(line)
    case 'json': return tokenizeJson(line)
    case 'python': case 'py': return tokenizePython(line)
    default: return esc(line)
  }
}

const lines = computed(() => (props.modelValue ?? '').split('\n'))
const highlighted = computed(() => lines.value.map(renderLine).join('\n') + '\n')

function onInput(event) { emit('update:modelValue', event.target.value) }
function onScroll() {
  if (!area.value) return
  if (back.value) { back.value.scrollTop = area.value.scrollTop; back.value.scrollLeft = area.value.scrollLeft }
  if (gutter.value) gutter.value.scrollTop = area.value.scrollTop
}
function onKeydown(event) {
  if (event.key === 'Tab' && !props.readonly) {
    event.preventDefault()
    const el = event.target, start = el.selectionStart, end = el.selectionEnd
    const next = el.value.slice(0, start) + '  ' + el.value.slice(end)
    emit('update:modelValue', next)
    requestAnimationFrame(() => { el.selectionStart = el.selectionEnd = start + 2 })
  }
}
</script>

<template>
  <div class="code-editor" :style="{ height: height + 'px' }">
    <div ref="gutter" class="gutter"><div v-for="n in lines.length" :key="n">{{ n }}</div></div>
    <div class="edit-area">
      <pre ref="back" class="highlight" aria-hidden="true"><code v-html="highlighted"/></pre>
      <textarea ref="area" class="input" :value="modelValue" :readonly="readonly" :placeholder="placeholder"
                spellcheck="false" @input="onInput" @scroll="onScroll" @keydown="onKeydown"/>
    </div>
  </div>
</template>

<style scoped>
.code-editor { display: flex; overflow: hidden; border: 1px solid var(--border-color); border-radius: 10px; background: var(--console-bg); box-shadow: inset 0 0 30px rgba(0, 0, 0, .28); }
.gutter { flex: 0 0 46px; overflow: hidden; padding: 14px 0; border-right: 1px solid rgba(255, 255, 255, .06); color: var(--text-muted); font: 13px/1.65 Consolas, monospace; text-align: right; opacity: .8; }
.gutter div { padding-right: 10px; }
.edit-area { position: relative; flex: 1; min-width: 0; }
.input { position: absolute; inset: 0; margin: 0; padding: 14px 16px; width: 100%; height: 100%; border: 0; box-sizing: border-box; font: 13px/1.65 Consolas, "JetBrains Mono", monospace; white-space: pre; overflow: auto; tab-size: 2; resize: none; outline: none; color: var(--text-primary); caret-color: #66e7ff; background: transparent; }
.input::selection { background: rgba(102, 231, 255, .25); }
.input::placeholder { color: var(--text-muted); }
.highlight { display: none; }
</style>
