<script setup>
defineProps({
  tree: { type: Array, required: true }, // [{ name, dir, children?, badge? }]
  title: { type: String, default: '目录结构' },
  height: { type: [String, Number], default: 'auto' },
})

const ICONS = {
  dir: 'M3 4h5l2 2h11a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Z',
  file: 'M6 2h8l4 4v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1Z',
}

function renderNodes(nodes, depth = 0) {
  return nodes.map((n) => ({
    ...n,
    _depth: depth,
    _children: n.children ? renderNodes(n.children, depth + 1) : null,
  }))
}
</script>

<template>
  <div class="tree-guide">
    <div v-if="title" class="tg-title">{{ title }}</div>
    <div class="tg-body" :style="{ maxHeight: typeof height === 'number' ? height + 'px' : height }">
      <template v-for="node in renderNodes(tree)" :key="node.name + node._depth + (node.badge || '')">
        <div class="tg-row" :style="{ paddingLeft: node._depth * 18 + 'px' }">
          <svg v-if="node.dir" class="tg-ico tg-dir" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path :d="ICONS.dir"/></svg>
          <svg v-else class="tg-ico tg-file" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path :d="ICONS.file"/></svg>
          <span class="tg-name" :class="{ 'tg-dirname': node.dir }">{{ node.name }}</span>
          <span v-if="node.badge" class="tg-badge">{{ node.badge }}</span>
        </div>
        <template v-if="node._children">
          <template v-for="child in node._children" :key="child.name + child._depth + (child.badge || '')">
            <div class="tg-row" :style="{ paddingLeft: child._depth * 18 + 'px' }">
              <svg v-if="child.dir" class="tg-ico tg-dir" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path :d="ICONS.dir"/></svg>
              <svg v-else class="tg-ico tg-file" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path :d="ICONS.file"/></svg>
              <span class="tg-name" :class="{ 'tg-dirname': child.dir }">{{ child.name }}</span>
              <span v-if="child.badge" class="tg-badge">{{ child.badge }}</span>
            </div>
          </template>
        </template>
      </template>
    </div>
  </div>
</template>

<style scoped>
.tree-guide { border: 1px solid var(--border-color); border-radius: 10px; background: var(--surface-soft); overflow: hidden; }
.tg-title { padding: 9px 14px; font-size: 12px; font-weight: 600; color: var(--text-secondary); background: var(--primary-glow); border-bottom: 1px solid var(--border-color); }
.tg-body { padding: 10px 12px; overflow-y: auto; font-family: Consolas, "SF Mono", Menlo, monospace; }
.tg-row { display: flex; align-items: center; gap: 7px; padding: 2.5px 0; font-size: 12.5px; line-height: 1.5; }
.tg-ico { width: 15px; height: 15px; flex: 0 0 auto; }
.tg-dir { color: var(--primary); }
.tg-file { color: var(--text-muted); }
.tg-name { color: var(--text-secondary); }
.tg-dirname { color: var(--text-primary); font-weight: 600; }
.tg-badge { margin-left: auto; font-size: 10.5px; color: var(--text-muted); padding: 1px 7px; border: 1px solid var(--border-color); border-radius: 20px; background: var(--surface); white-space: nowrap; }
</style>
