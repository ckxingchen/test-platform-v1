<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: String, default: '' },
  label: { type: String, default: '' }
})

const LABELS = {
  success: '成功', failed: '失败', canceled: '已取消', timeout: '超时',
  running: '运行中', queued: '排队中', dispatching: '调度中',
  passed: '通过', skipped: '跳过', error: '错误',
  online: '在线', offline: '离线', pending: '待注册',
  not_deployed: '未部署', deploying: '部署中', ready: '已就绪',
  update_available: '有更新', enabled: '启用', disabled: '停用'
}

const kind = computed(() => {
  const v = (props.value || '').toLowerCase()
  if (['success', 'passed', 'online', 'ready', 'enabled'].includes(v)) return 'success'
  if (['failed', 'error', 'timeout', 'offline'].includes(v)) return 'failed'
  if (['running', 'dispatching', 'deploying'].includes(v)) return 'running'
  return 'queued'
})
const text = computed(() => props.label || LABELS[(props.value || '').toLowerCase()] || props.value || '-')
</script>

<template>
  <span :class="`status status-${kind}`">{{ text }}</span>
</template>
