<script setup>
import { computed, ref, watch } from 'vue'

// 结构化 INI 编辑器：按「配置节 → 参数表格」展示。
// 参数名（key）只读不可增删，仅允许修改参数值（value），防止用户随意增加配置项。
// 注释行自动归属到下方最近的参数，作为参数说明展示。
const props = defineProps({
  modelValue: { type: String, default: '' },
  height: { type: Number, default: 540 }  // 弹窗内可用高度（含滚动），默认 540
})
const emit = defineEmits(['update:modelValue'])

function parseIni(text) {
  const sections = []
  let current = null
  let pendingComment = ''
  for (const raw of String(text ?? '').split('\n')) {
    const line = raw.trim()
    if (!line) { pendingComment = ''; continue }
    if (line.startsWith('[') && line.endsWith(']')) {
      current = { section: line.slice(1, -1).trim(), comment: pendingComment, params: [] }
      sections.push(current)
      pendingComment = ''
      continue
    }
    if (line.startsWith('#') || line.startsWith(';')) {
      pendingComment = pendingComment ? `${pendingComment} ${line.replace(/^[;#]\s*/, '')}` : line.replace(/^[;#]\s*/, '')
      continue
    }
    const eq = line.indexOf('=')
    if (eq > 0) {
      if (!current) {
        current = { section: '默认配置', comment: '', params: [] }
        sections.push(current)
      }
      current.params.push({
        key: line.slice(0, eq).trim(),
        value: line.slice(eq + 1).trim(),
        comment: pendingComment
      })
      pendingComment = ''
    }
  }
  return sections
}

function serializeIni(sections) {
  const blocks = []
  for (const group of sections) {
    const lines = []
    if (group.section) lines.push(`[${group.section}]`)
    if (group.comment) lines.push(`#${group.comment}`)
    for (const param of group.params) {
      if (param.comment) lines.push(`#${param.comment}`)
      lines.push(`${param.key} = ${param.value}`)
    }
    blocks.push(lines.join('\n'))
  }
  return blocks.join('\n\n')
}

const sections = ref([])
const activeNames = ref([])  // el-collapse 展开项名称数组
const parseFailed = ref(false)

function reload(text) {
  try {
    const parsed = parseIni(text)
    parseFailed.value = parsed.every(s => !s.params.length)
    sections.value = parsed
    // 默认展开所有配置节（按需可由 activeNames 控制收起）
    activeNames.value = parsed.map(s => s.section)
  } catch {
    parseFailed.value = true
  }
}

watch(() => props.modelValue, (text) => {
  // 回环保护：自己 emit 的序列化结果不再重新解析
  if (serializeIni(sections.value) === text) return
  reload(text)
}, { immediate: true })

const paramCount = computed(() => sections.value.reduce((sum, s) => sum + s.params.length, 0))

function onValueChange() {
  emit('update:modelValue', serializeIni(sections.value))
}
</script>

<template>
  <div class="ini-editor" :style="{ maxHeight: height + 'px' }">
    <template v-if="!parseFailed">
      <div v-if="!sections.length" class="muted empty-all">配置文件为空</div>
      <el-collapse v-model="activeNames">
        <el-collapse-item v-for="group in sections" :key="group.section" :name="group.section" class="ini-section">
          <template #title>
            <div class="section-title">
              <span class="section-name">{{ group.section || '默认配置' }}</span>
              <span class="section-meta">{{ group.params.length }} 个参数</span>
            </div>
          </template>
          <p v-if="group.comment" class="section-comment">{{ group.comment }}</p>
          <table v-if="group.params.length" class="param-table">
            <colgroup><col style="width:200px"><col><col style="width:42%"></colgroup>
            <thead><tr><th>参数</th><th>值</th><th>说明</th></tr></thead>
            <tbody>
              <tr v-for="param in group.params" :key="group.section + param.key">
                <td><code class="param-key">{{ param.key }}</code></td>
                <td><el-input v-model="param.value" size="small" class="param-input" @change="onValueChange"/></td>
                <td><span class="param-comment">{{ param.comment || '-' }}</span></td>
              </tr>
            </tbody>
          </table>
          <div v-else class="muted empty-section">该节暂无参数</div>
        </el-collapse-item>
      </el-collapse>
      <div class="ini-foot">共 {{ sections.length }} 个配置节 · {{ paramCount }} 个参数（参数名固定，仅可修改参数值）</div>
    </template>
    <template v-else>
      <el-alert type="warning" :closable="false" title="配置文件格式无法结构化解析，已切换为纯文本模式（只读）"/>
      <pre class="raw-text">{{ modelValue }}</pre>
    </template>
  </div>
</template>

<style scoped>
.ini-editor { border: 1px solid var(--border-color); border-radius: 10px; background: var(--surface); padding: 4px 12px 10px; display: flex; flex-direction: column; gap: 6px; }
.ini-editor :deep(.el-collapse) { border: none; }
.ini-editor :deep(.el-collapse-item__header) { background: var(--surface-soft); border: 1px solid var(--border-color); border-radius: 8px; padding: 0 14px; margin-bottom: 6px; }
.ini-editor :deep(.el-collapse-item__header.is-active) { border-bottom-left-radius: 0; border-bottom-right-radius: 0; border-bottom-color: transparent; }
.ini-editor :deep(.el-collapse-item__wrap) { border: 1px solid var(--border-color); border-top: 0; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; overflow: hidden; margin-bottom: 6px; background: var(--surface-solid); }
.ini-editor :deep(.el-collapse-item__content) { padding: 0; }
.section-title { display: flex; align-items: center; gap: 12px; width: 100%; }
.section-name { color: var(--primary); font-weight: 700; font-size: 13px; font-family: Consolas, monospace; }
.section-meta { color: var(--text-muted); font-size: 12px; }
.section-comment { margin: 10px 14px 4px; padding: 6px 10px; color: var(--text-secondary); font-size: 12px; line-height: 1.6; background: var(--surface-soft); border-left: 2px solid var(--primary); border-radius: 0 4px 4px 0; }
.param-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.param-table th { text-align: left; padding: 8px 14px; color: var(--text-muted); font-size: 12px; font-weight: 600; border-bottom: 1px solid var(--border-color); background: var(--surface); }
.param-table td { padding: 6px 14px; border-bottom: 1px solid var(--border-color); vertical-align: middle; }
.param-table tr:last-child td { border-bottom: 0; }
.param-key { font-family: Consolas, monospace; font-size: 12.5px; color: var(--text-primary); word-break: break-all; }
.param-input :deep(.el-input__wrapper) { box-shadow: none; background: var(--surface-soft); }
.param-comment { color: var(--text-secondary); font-size: 12px; line-height: 1.5; word-break: break-all; }
.empty-section { padding: 12px 14px; font-size: 12px; }
.empty-all { padding: 30px; text-align: center; font-size: 13px; }
.ini-foot { color: var(--text-muted); font-size: 12px; text-align: center; padding: 4px 0 2px; }
.raw-text { margin: 12px 0 0; padding: 14px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--console-bg); color: var(--text-primary); font: 12.5px/1.6 Consolas, monospace; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow: auto; }
</style>
