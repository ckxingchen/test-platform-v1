<script setup>
import { computed, reactive, watch } from 'vue'

// 从扁平路径数组构建的可展开树。点击文件/目录均可选中。
const props = defineProps({
  paths: { type: Array, default: () => [] }, // ['testcase/01登录/a.yaml', ...]
  selected: { type: String, default: '' },
  height: { type: Number, default: 0 }, // 0 = 不限制
  emptyText: { type: String, default: '暂无文件' }
})
const emit = defineEmits(['select'])

const collapsed = reactive(new Set())

// 构建嵌套树
const tree = computed(() => {
  const root = { name: '', path: '', children: new Map(), isDir: true }
  for (const raw of props.paths) {
    const parts = String(raw).split('/').filter(Boolean)
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

// 拍平为可见行（含层级），目录默认展开
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

function click(row) {
  if (row.isDir && row.hasChildren) {
    collapsed.has(row.path) ? collapsed.delete(row.path) : collapsed.add(row.path)
  }
  emit('select', row)
}
</script>

<template>
  <div class="path-tree" :style="height ? { height: height + 'px' } : {}">
    <div v-for="row in rows" :key="row.path" class="node" :class="{ active: selected === row.path, dir: row.isDir }"
         :style="{ paddingLeft: 10 + row.depth * 16 + 'px' }" @click="click(row)">
      <span class="arrow" :class="{ hidden: !row.isDir || !row.hasChildren }">{{ collapsed.has(row.path) ? '▸' : '▾' }}</span>
      <svg v-if="row.isDir" class="icon folder" viewBox="0 0 16 16" fill="currentColor"><path d="M1.5 2.5h4l1.5 2h7.5v8a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1z" opacity=".85"/></svg>
      <svg v-else class="icon file" viewBox="0 0 16 16" fill="currentColor"><path d="M3.5 1.5h6L13 5v8.5a1 1 0 0 1-1 1H3.5a1 1 0 0 1-1-1v-11a1 1 0 0 1 1-1zm5.5 1v3h3" opacity=".7"/></svg>
      <span class="name">{{ row.name }}</span>
    </div>
    <div v-if="!rows.length" class="tree-empty">{{ emptyText }}</div>
  </div>
</template>

<style scoped>
.path-tree { overflow: auto; padding: 6px; border: 1px solid var(--border-color); border-radius: 10px; background: var(--surface-soft); font-size: 12.5px; }
.node { display: flex; align-items: center; gap: 6px; padding: 4px 8px 4px 0; border-radius: 7px; color: var(--text-secondary); cursor: pointer; user-select: none; white-space: nowrap; }
.node:hover { background: var(--surface-hover); color: var(--text-primary); }
.node.active { background: var(--primary-glow); color: var(--primary); font-weight: 600; }
.node.dir { color: var(--text-primary); }
.arrow { width: 12px; flex: 0 0 12px; color: var(--text-muted); font-size: 10px; text-align: center; }
.arrow.hidden { visibility: hidden; }
.icon { width: 13px; height: 13px; flex: 0 0 13px; }
.icon.folder { color: var(--warning); }
.icon.file { color: var(--text-muted); }
.name { overflow: hidden; text-overflow: ellipsis; }
.tree-empty { padding: 20px; color: var(--text-muted); text-align: center; font-size: 12px; }
</style>
