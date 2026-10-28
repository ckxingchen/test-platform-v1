<script setup>
import { computed, reactive, watch } from 'vue'

// 从扁平路径数组构建的可多选勾选用例树。
// 隐藏 testcase/casedata/ 与框架前后置 yml，仅展示可运行用例（文件或目录）。
const props = defineProps({
  paths: { type: Array, default: () => [] }, // ['testcase/01登录/a.yaml', ...]
  modelValue: { type: Array, default: () => [] }, // 已勾选的完整相对路径（含 testcase/ 前缀）
  height: { type: Number, default: 0 },
  emptyText: { type: String, default: '暂无文件' },
  showHidden: { type: Boolean, default: false } // 为 true 时展示全部文件（含 casedata 与前后置 yml），用于上传场景
})
const emit = defineEmits(['update:modelValue'])

const collapsed = reactive(new Set())

// 需隐藏的文件名（casedata 目录、前后置 yml）
const HIDDEN_NAMES = new Set([
  'casedata',
  '测试集前置.yaml', '测试集前置.yml',
  '测试集后置.yaml', '测试集后置.yml',
  '测试用例前置.yaml', '测试用例前置.yml',
  '测试用例后置.yaml', '测试用例后置.yml',
])

// 过滤后构建嵌套树
const tree = computed(() => {
  const root = { name: '', path: '', children: new Map(), isDir: true }
  for (const raw of props.paths) {
    const parts = String(raw).split('/').filter(Boolean)
    if (!props.showHidden && parts.some(p => HIDDEN_NAMES.has(p))) continue
    let node = root
    parts.forEach((part, index) => {
      const path = parts.slice(0, index + 1).join('/')
      if (!node.children.has(part)) node.children.set(part, { name: part, path, children: new Map(), isDir: index < parts.length - 1 })
      node = node.children.get(part)
      if (index < parts.length - 1) node.isDir = true
    })
  }
  return root
})

const rows = computed(() => {
  const out = []
  const walk = (node, depth) => {
    const kids = [...node.children.values()].sort((a, b) => (b.isDir - a.isDir) || a.name.localeCompare(b.name, 'zh'))
    for (const kid of kids) {
      out.push({ name: kid.name, path: kid.path, isDir: kid.isDir, depth, hasChildren: kid.children.size > 0 })
      if (kid.isDir && kid.children.size && !collapsed.has(kid.path)) walk(kid, depth + 1)
    }
  }
  walk(tree.value, 0)
  return out
})

watch(() => props.paths.length, () => collapsed.clear())

const selectedSet = computed(() => new Set(props.modelValue || []))

function isChecked(row) {
  // 目录：自身被勾选，或其所有直接子项都被勾选视为全选
  if (!row.isDir) return selectedSet.value.has(row.path)
  const children = collectDescendants(row.path)
  if (!children.length) return selectedSet.value.has(row.path)
  return children.every(c => selectedSet.value.has(c.path))
}
function isIndeterminate(row) {
  if (!row.isDir) return false
  const children = collectDescendants(row.path)
  if (!children.length) return false
  const checked = children.filter(c => selectedSet.value.has(c.path)).length
  return checked > 0 && checked < children.length
}
function collectDescendants(dirPath) {
  const out = []
  for (const r of rows.value) {
    if (r.path.startsWith(dirPath + '/') && !r.isDir) out.push(r)
  }
  return out
}

function toggle(row) {
  let next = new Set(selectedSet.value)
  if (row.isDir) {
    const descendants = collectDescendants(row.path)
    const leafPaths = descendants.map(c => c.path)
    // 无文件子项时按目录自身路径处理
    const targets = leafPaths.length ? leafPaths : [row.path]
    const allChecked = targets.every(p => next.has(p))
    if (allChecked) targets.forEach(p => next.delete(p))
    else targets.forEach(p => next.add(p))
  } else {
    next.has(row.path) ? next.delete(row.path) : next.add(row.path)
  }
  emit('update:modelValue', [...next])
}

function click(row) {
  if (row.isDir && row.hasChildren) {
    collapsed.has(row.path) ? collapsed.delete(row.path) : collapsed.add(row.path)
  }
}
</script>

<template>
  <div class="case-check-tree" :style="height ? { height: height + 'px' } : {}">
    <div v-for="row in rows" :key="row.path" class="node" :style="{ paddingLeft: 10 + row.depth * 16 + 'px' }">
      <span class="arrow" :class="{ hidden: !row.isDir || !row.hasChildren }" @click.stop="click(row)">
        {{ collapsed.has(row.path) ? '▸' : '▾' }}
      </span>
      <label class="check" @click.stop="toggle(row)">
        <input type="checkbox" :checked="isChecked(row)" :indeterminate="isIndeterminate(row)" @click.stop>
        <span class="box" :class="{ on: isChecked(row), part: isIndeterminate(row) }"></span>
      </label>
      <span class="icon-wrap" @click.stop="click(row)">
        <svg v-if="row.isDir" class="icon folder" viewBox="0 0 16 16" fill="currentColor"><path d="M1.5 2.5h4l1.5 2h7.5v8a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1z" opacity=".85"/></svg>
        <svg v-else class="icon file" viewBox="0 0 16 16" fill="currentColor"><path d="M3.5 1.5h6L13 5v8.5a1 1 0 0 1-1 1H3.5a1 1 0 0 1-1-1v-11a1 1 0 0 1 1-1zm5.5 1v3h3" opacity=".7"/></svg>
      </span>
      <span class="name" @click.stop="toggle(row)">{{ row.name }}</span>
    </div>
    <div v-if="!rows.length" class="tree-empty">{{ emptyText }}</div>
  </div>
</template>

<style scoped>
.case-check-tree { overflow: auto; padding: 6px; border: 1px solid var(--border-color); border-radius: 10px; background: var(--surface-soft); font-size: 12.5px; }
.node { display: flex; align-items: center; gap: 6px; padding: 4px 8px 4px 0; border-radius: 7px; color: var(--text-secondary); user-select: none; white-space: nowrap; }
.node:hover { background: var(--surface-hover); color: var(--text-primary); }
.arrow { width: 12px; flex: 0 0 12px; color: var(--text-muted); font-size: 10px; text-align: center; cursor: pointer; }
.arrow.hidden { visibility: hidden; }
.check { display: inline-flex; align-items: center; cursor: pointer; }
.check input { position: absolute; opacity: 0; width: 0; height: 0; }
.box { width: 14px; height: 14px; flex: 0 0 14px; border: 1.5px solid var(--border-strong); border-radius: 4px; background: var(--surface); display: inline-block; position: relative; transition: .15s; }
.box.on { background: var(--primary); border-color: var(--primary); }
.box.on::after { content: ''; position: absolute; left: 4px; top: 1px; width: 4px; height: 8px; border: solid #fff; border-width: 0 2px 2px 0; transform: rotate(45deg); }
.box.part { background: var(--primary); border-color: var(--primary); }
.box.part::after { content: ''; position: absolute; left: 3px; top: 5px; width: 6px; height: 2px; background: #fff; }
.icon-wrap { display: inline-flex; cursor: pointer; }
.icon { width: 13px; height: 13px; flex: 0 0 13px; }
.icon.folder { color: var(--warning); }
.icon.file { color: var(--text-muted); }
.name { overflow: hidden; text-overflow: ellipsis; cursor: pointer; }
.tree-empty { padding: 20px; color: var(--text-muted); text-align: center; font-size: 12px; }
</style>
