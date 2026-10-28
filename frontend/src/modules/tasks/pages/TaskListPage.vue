<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { auth } from '@/platform/auth/session'
import { TERM } from '@/shared/constants/terminology'
import StatusBadge from '@/shared/components/StatusBadge.vue'

const ACTIVE = ['queued', 'dispatching', 'running']
const TERMINAL = ['success', 'failed', 'canceled', 'timeout']
const STATUS_OPTIONS = [
  { value: '', label: '全部状态' }, { value: 'queued', label: '排队中' }, { value: 'running', label: '运行中' },
  { value: 'success', label: '成功' }, { value: 'failed', label: '失败' }, { value: 'canceled', label: '已取消' }, { value: 'timeout', label: '超时' }
]

const router = useRouter()
const rows = ref([])
const loading = ref(false), refreshedAt = ref(null)
const filterStatus = ref(''), filterProject = ref(null), filterEnv = ref(null), keyword = ref('')
const groupByProject = ref(false)
const page = ref(1), pageSize = ref(20)
const selection = ref([])
let timer = null

const canOperate = computed(() => auth.user?.role !== 'viewer')

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    const tasks = await api.get('/tasks')
    rows.value = [...tasks.data].sort((a, b) => b.id - a.id)
    refreshedAt.value = new Date()
  } finally { loading.value = false }
}

// 筛选下拉选项直接从任务数据去重（任务已携带 project_name / environment_name）
const projectOptions = computed(() => {
  const map = new Map()
  for (const row of rows.value) if (row.project_id && !map.has(row.project_id)) map.set(row.project_id, { id: row.project_id, name: row.project_name || `#${row.project_id}` })
  return [...map.values()]
})
const environmentOptions = computed(() => {
  const map = new Map()
  for (const row of rows.value) if (row.environment_id && !map.has(row.environment_id)) map.set(row.environment_id, { id: row.environment_id, name: row.environment_name || `#${row.environment_id}` })
  return [...map.values()]
})

const filtered = computed(() => rows.value.filter(row => {
  if (filterStatus.value) {
    if (filterStatus.value === 'running') { if (!ACTIVE.includes(row.status)) return false }
    else if (row.status !== filterStatus.value) return false
  }
  if (filterProject.value && row.project_id !== filterProject.value) return false
  if (filterEnv.value && row.environment_id !== filterEnv.value) return false
  if (keyword.value) {
    const kw = keyword.value.toLowerCase()
    const hay = `${row.id} ${row.project_name || ''} ${row.environment_name || ''} ${(row.testcase_scope?.path || '')}`.toLowerCase()
    if (!hay.includes(kw)) return false
  }
  return true
}))

const paged = computed(() => {
  const list = [...filtered.value]
  if (groupByProject.value) list.sort((a, b) => (a.project_id - b.project_id) || (b.id - a.id))
  return list.slice((page.value - 1) * pageSize.value, page.value * pageSize.value)
})

const statusCount = computed(() => {
  const count = { active: 0, failed: 0 }
  for (const row of rows.value) {
    if (ACTIVE.includes(row.status)) count.active++
    if (row.status === 'failed' || row.status === 'timeout') count.failed++
  }
  return count
})

// 按项目分组：合并「测试项目」列（第 3 列，下标 2）连续同项目单元格
function spanMethod({ rowIndex, columnIndex }) {
  if (!groupByProject.value || columnIndex !== 2) return [1, 1]
  const list = paged.value
  if (rowIndex > 0 && list[rowIndex].project_id === list[rowIndex - 1].project_id) return [0, 0]
  let count = 1
  for (let i = rowIndex + 1; i < list.length; i++) {
    if (list[i].project_id === list[rowIndex].project_id) count++
    else break
  }
  return [count, 1]
}

watch([filterStatus, filterProject, filterEnv, keyword, groupByProject], () => { page.value = 1 })

function duration(row) {
  if (!row.started_at) return '-'
  const end = row.finished_at ? new Date(row.finished_at) : new Date()
  const sec = Math.max(0, Math.round((end - new Date(row.started_at)) / 1000))
  if (sec < 60) return `${sec} 秒`
  if (sec < 3600) return `${Math.floor(sec / 60)} 分 ${sec % 60} 秒`
  return `${Math.floor(sec / 3600)} 时 ${Math.floor((sec % 3600) / 60)} 分`
}

function onSelectionChange(list) { selection.value = list }
const cancelable = computed(() => selection.value.filter(x => ACTIVE.includes(x.status)))
const rerunable = computed(() => selection.value.filter(x => TERMINAL.includes(x.status)))

async function batchCancel() {
  if (!cancelable.value.length) return ElMessage.warning('所选任务中没有可取消（排队/运行中）的任务')
  await ElMessageBox.confirm(`确认取消选中的 ${cancelable.value.length} 个任务？`, '批量取消', { type: 'warning' })
  let ok = 0
  for (const row of cancelable.value) {
    try { await api.post(`/tasks/${row.id}/cancel`); ok++ } catch { /* 拦截器已提示 */ }
  }
  ElMessage.success(`已提交取消 ${ok} 个任务`)
  load(true)
}

async function batchRerun() {
  if (!rerunable.value.length) return ElMessage.warning('所选任务中没有可重跑（已终态）的任务')
  await ElMessageBox.confirm(`确认重跑选中的 ${rerunable.value.length} 个任务？将创建同等配置的新任务。`, '批量重跑', { type: 'warning' })
  let ok = 0
  for (const row of rerunable.value) {
    try { await api.post(`/tasks/${row.id}/rerun`); ok++ } catch { /* 拦截器已提示 */ }
  }
  ElMessage.success(`已创建 ${ok} 个重跑任务`)
  load(true)
}

function startTimer() {
  clearInterval(timer)
  timer = setInterval(() => {
    if (document.visibilityState === 'visible' && rows.value.some(x => ACTIVE.includes(x.status))) load(true)
  }, 5000)
}

onMounted(() => { load(); startTimer() })
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div><h2>{{ TERM.task }}</h2><div class="muted">共 {{ rows.length }} 个任务 · {{ statusCount.active }} 个进行中 · {{ statusCount.failed }} 个失败<span v-if="refreshedAt"> · 更新于 {{ refreshedAt.toLocaleTimeString() }}</span></div></div>
      <div class="toolbar">
        <template v-if="canOperate">
          <el-button :disabled="!cancelable.length" type="danger" plain @click="batchCancel">批量取消<template v-if="cancelable.length"> ({{ cancelable.length }})</template></el-button>
          <el-button :disabled="!rerunable.length" plain @click="batchRerun">批量重跑<template v-if="rerunable.length"> ({{ rerunable.length }})</template></el-button>
        </template>
        <el-button @click="load()">刷新</el-button>
        <el-button v-if="canOperate" type="primary" @click="router.push('/tasks/create')">新建任务</el-button>
      </div>
    </div>

    <div class="card filters">
      <el-select v-model="filterStatus" placeholder="状态" clearable style="width:130px">
        <el-option v-for="item in STATUS_OPTIONS" :key="item.value" :label="item.label" :value="item.value"/>
      </el-select>
      <el-select v-model="filterProject" placeholder="测试项目" clearable filterable style="width:200px">
        <el-option v-for="item in projectOptions" :key="item.id" :label="item.name" :value="item.id"/>
      </el-select>
      <el-select v-model="filterEnv" placeholder="执行器" clearable filterable style="width:200px">
        <el-option v-for="item in environmentOptions" :key="item.id" :label="item.name" :value="item.id"/>
      </el-select>
      <el-input v-model="keyword" placeholder="搜索任务 ID / 项目 / 执行器 / 用例路径" clearable style="width:280px"/>
      <el-switch v-model="groupByProject" active-text="按项目分组"/>
      <span class="muted">匹配 {{ filtered.length }} 条</span>
    </div>

    <div class="card">
      <el-table v-loading="loading" :data="paged" :span-method="spanMethod" @selection-change="onSelectionChange">
        <el-table-column type="selection" width="42" :selectable="() => canOperate"/>
        <el-table-column prop="id" label="任务 ID" width="90" sortable/>
        <el-table-column label="测试项目" min-width="150"><template #default="{row}"><el-link type="primary" @click="router.push(`/objects/projects/${row.project_id}`)">{{ row.project_name || row.project_id }}</el-link></template></el-table-column>
        <el-table-column label="执行器" min-width="140"><template #default="{row}"><el-link type="primary" @click="router.push(`/executors/${row.environment_id}`)">{{ row.environment_name || row.environment_id }}</el-link></template></el-table-column>
        <el-table-column label="测试框架" min-width="140"><template #default="{row}">{{ row.framework_name || row.framework_id || '-' }}</template></el-table-column>
        <el-table-column label="状态" width="110"><template #default="{row}"><StatusBadge :value="row.status"/></template></el-table-column>
        <el-table-column label="耗时" width="110"><template #default="{row}">{{ duration(row) }}</template></el-table-column>
        <el-table-column label="创建人" min-width="110"><template #default="{row}">{{ row.created_by_name || '-' }}</template></el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" sortable><template #default="{row}">{{ new Date(row.created_at).toLocaleString() }}</template></el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" @click="router.push(`/tasks/${row.id}`)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="filtered.length"
                       :page-sizes="[10, 20, 50, 100]" layout="total, sizes, prev, pager, next, jumper" background/>
      </div>
    </div>
  </div>
</template>

<style scoped>
.filters { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; padding: 14px 18px; }
.path { font-family: Consolas, monospace; font-size: 12px; color: var(--text-secondary); }
.pager { display: flex; justify-content: flex-end; margin-top: 14px; }
</style>
