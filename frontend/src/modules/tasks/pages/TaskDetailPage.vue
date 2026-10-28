<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { api, download } from '../api'
import { auth } from '@/platform/auth/session'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import LogConsole from '@/shared/components/LogConsole.vue'
import StatBar from '@/shared/components/StatBar.vue'

const route = useRoute(), router = useRouter(), id = route.params.id
const task = ref({}), logs = ref([]), results = ref([]), artifacts = ref([]), users = ref({})
const tab = ref('logs')
const resultStatus = ref(''), resultKeyword = ref('')
const preview = ref({ visible: false, url: '', name: '' })
const streamState = ref('idle')
const logIds = new Set()
let socket, timer, reconnectTimer
let reconnectAttempts = 0
let realtimeStopped = false

const TERMINAL = ['success', 'failed', 'canceled', 'timeout']
const RESULT_LABELS = { passed: '通过', failed: '失败', skipped: '跳过', error: '错误' }
const RESULT_TONES = { passed: 'success', failed: 'danger', error: 'danger', skipped: 'warning' }

async function load() {
  task.value = (await api.get(`/tasks/${id}`)).data
  results.value = (await api.get(`/tasks/${id}/results`)).data
  artifacts.value = (await api.get(`/tasks/${id}/artifacts`)).data
}

function lastLogId() {
  for (let index = logs.value.length - 1; index >= 0; index--) {
    if (logs.value[index]?.id) return logs.value[index].id
  }
  return ''
}

function mergeLogs(incoming, replace = false) {
  if (replace) logIds.clear()
  const additions = []
  for (const item of incoming || []) {
    if (item.id && logIds.has(item.id)) continue
    additions.push(item)
    if (item.id) logIds.add(item.id)
  }
  if (replace) logs.value = additions
  else if (additions.length) logs.value = logs.value.concat(additions)
}

async function loadLogs(replace = false) {
  const cursor = replace ? '' : lastLogId()
  const response = await api.get(`/tasks/${id}/logs`, {
    params: cursor ? { after_id: cursor } : undefined
  })
  mergeLogs(response.data.logs, replace)
}

function connect() {
  if (realtimeStopped || !auth.token) return
  clearTimeout(reconnectTimer)
  streamState.value = reconnectAttempts ? 'reconnecting' : 'connecting'
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  const cursor = lastLogId() || '0-0'
  socket = new WebSocket(
    `${protocol}://${location.host}/api/v1/ws/tasks/${id}?last_id=${encodeURIComponent(cursor)}`,
    ['bearer', auth.token]
  )
  socket.onopen = () => {
    reconnectAttempts = 0
    streamState.value = 'connected'
  }
  socket.onmessage = event => {
    const item = JSON.parse(event.data)
    if (item.type === 'logs' && Array.isArray(item.logs)) mergeLogs(item.logs)
    else if (item.message) mergeLogs([item]) // 兼容旧版平台的单行消息
  }
  socket.onerror = () => { streamState.value = 'fallback' }
  socket.onclose = () => {
    if (realtimeStopped) return
    streamState.value = 'fallback'
    reconnectAttempts += 1
    reconnectTimer = setTimeout(connect, Math.min(1000 * (2 ** (reconnectAttempts - 1)), 10000))
  }
}

const streamStateLabel = computed(() => ({
  idle: '等待连接',
  connecting: '正在连接实时日志',
  reconnecting: '实时连接重试中',
  connected: '实时连接正常',
  fallback: '实时连接中断，已切换轮询',
  complete: '日志已归档'
}[streamState.value] || '日志状态未知'))

async function cancel() { await ElMessageBox.confirm('确认取消任务？'); await api.post(`/tasks/${id}/cancel`); load() }
async function rerun() { const row = (await api.post(`/tasks/${id}/rerun`)).data; router.push(`/tasks/${row.id}`) }
function clone() { router.push({ path: '/tasks/create', query: { clone: id } }) }

// 结果统计与筛选
const segments = computed(() => {
  const count = {}
  for (const row of results.value) count[row.status] = (count[row.status] || 0) + 1
  const order = ['passed', 'failed', 'error', 'skipped']
  const keys = [...order.filter(k => count[k]), ...Object.keys(count).filter(k => !order.includes(k))]
  return keys.map(k => ({ key: k, label: RESULT_LABELS[k] || k, count: count[k], tone: RESULT_TONES[k] || 'muted', main: k === 'passed' }))
})
const filteredResults = computed(() => results.value.filter(row => {
  if (resultStatus.value && row.status !== resultStatus.value) return false
  if (resultKeyword.value) {
    const kw = resultKeyword.value.toLowerCase()
    if (!`${row.case_name} ${row.case_path}`.toLowerCase().includes(kw)) return false
  }
  return true
}))
const statusOptions = computed(() => [...new Set(results.value.map(x => x.status))].map(v => ({ value: v, label: RESULT_LABELS[v] || v })))

const duration = computed(() => {
  if (!task.value.started_at) return '-'
  const end = task.value.finished_at ? new Date(task.value.finished_at) : new Date()
  const sec = Math.max(0, Math.round((end - new Date(task.value.started_at)) / 1000))
  if (sec < 60) return `${sec} 秒`
  if (sec < 3600) return `${Math.floor(sec / 60)} 分 ${sec % 60} 秒`
  return `${Math.floor(sec / 3600)} 时 ${Math.floor((sec % 3600) / 60)} 分`
})

// 用例范围展示：优先 selected_case_paths（多选），兼容旧 testcase_scope.path
const caseScopeLabel = computed(() => {
  const paths = task.value.selected_case_paths
  if (Array.isArray(paths) && paths.length) return paths.join('；')
  return task.value.testcase_scope?.path || '整个项目'
})

// 报告在线预览
function isPreviewable(row) { return /\.(html?|txt|log|xml|json)$/i.test(row.object_key) }
async function openPreview(row) {
  const { data } = await api.get(`/tasks/${id}/artifacts/${row.id}/download`, { responseType: 'blob' })
  const type = /\.html?$/i.test(row.object_key) ? 'text/html' : 'text/plain'
  preview.value = { visible: true, url: URL.createObjectURL(new Blob([data], { type })), name: row.object_key.split('/').pop() }
}
function closePreview() { URL.revokeObjectURL(preview.value.url); preview.value = { visible: false, url: '', name: '' } }

onMounted(async () => {
  await Promise.all([load(), loadLogs(true)])
  if (!TERMINAL.includes(task.value.status)) connect()
  else streamState.value = 'complete'
  timer = setInterval(async () => {
    await load()
    if (streamState.value !== 'connected') await loadLogs()
    if (TERMINAL.includes(task.value.status)) {
      await loadLogs()
      clearInterval(timer)
      clearTimeout(reconnectTimer)
      realtimeStopped = true
      streamState.value = 'complete'
      socket?.close()
    }
  }, 2000)
})
onBeforeUnmount(() => {
  realtimeStopped = true
  clearInterval(timer)
  clearTimeout(reconnectTimer)
  socket?.close()
  if (preview.value.url) URL.revokeObjectURL(preview.value.url)
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div><el-button link @click="router.push('/tasks')">← 返回任务</el-button><h2>任务 #{{ id }} <StatusBadge :value="task.status"/></h2></div>
      <div class="toolbar">
        <el-button v-if="!TERMINAL.includes(task.status)" type="danger" plain @click="cancel">取消任务</el-button>
        <template v-if="TERMINAL.includes(task.status) && auth.user?.role !== 'viewer'">
          <el-button @click="clone">克隆任务</el-button>
          <el-button type="primary" @click="rerun">重新运行</el-button>
        </template>
      </div>
    </div>

    <div class="overview">
      <div><span>测试项目</span><b><el-link type="primary" @click="router.push(`/objects/projects/${task.project_id}`)">{{ task.project_name || task.project_id }}</el-link></b></div>
      <div><span>执行器</span><b><el-link type="primary" @click="router.push(`/executors/${task.environment_id}`)">{{ task.environment_name || task.environment_id }}</el-link></b></div>
      <div><span>测试框架</span><b>{{ task.framework_name || task.framework_id }}</b></div>
      <div><span>用例范围</span><b class="path">{{ caseScopeLabel }}</b></div>
      <div><span>超时上限</span><b>{{ task.timeout_seconds ? Math.round(task.timeout_seconds / 60) + ' 分钟' : '-' }}</b></div>
      <div><span>退出码</span><b>{{ task.exit_code ?? '-' }}</b></div>
      <div><span>耗时</span><b>{{ duration }}</b></div>
      <div><span>创建时间</span><b>{{ task.created_at ? new Date(task.created_at).toLocaleString() : '-' }}</b></div>
      <div><span>完成时间</span><b>{{ task.finished_at ? new Date(task.finished_at).toLocaleString() : '-' }}</b></div>
    </div>

    <el-alert v-if="task.error_message" :title="task.error_message" type="error" show-icon :closable="false"/>

    <div class="card tabs">
      <el-tabs v-model="tab">
        <el-tab-pane name="logs">
          <template #label>实时日志 <span class="tab-count">{{ logs.length }}</span></template>
          <div class="stream-state" :class="streamState"><i/>{{ streamStateLabel }}</div>
          <LogConsole :logs="logs" :filename="`task-${id}.log`"/>
        </el-tab-pane>

        <el-tab-pane name="results">
          <template #label>用例结果 <span class="tab-count">{{ results.length }}</span></template>
          <div class="result-tools">
            <StatBar :segments="segments" title="执行结果"/>
            <div class="result-filter">
              <el-radio-group v-model="resultStatus" size="small">
                <el-radio-button value="">全部</el-radio-button>
                <el-radio-button v-for="item in statusOptions" :key="item.value" :value="item.value">{{ item.label }}</el-radio-button>
              </el-radio-group>
              <el-input v-model="resultKeyword" size="small" placeholder="搜索用例名称 / 路径" clearable style="width:220px"/>
              <span class="muted">{{ filteredResults.length }} / {{ results.length }}</span>
            </div>
          </div>
          <el-table :data="filteredResults" row-key="id">
            <el-table-column type="expand">
              <template #default="{row}">
                <div class="error-detail">
                  <template v-if="row.error_message"><b>错误详情</b><pre>{{ row.error_message }}</pre></template>
                  <span v-else class="muted">该用例无错误信息</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="case_name" label="用例" min-width="200" show-overflow-tooltip/>
            <el-table-column prop="case_path" label="路径" min-width="260" show-overflow-tooltip><template #default="{row}"><span class="path">{{ row.case_path }}</span></template></el-table-column>
            <el-table-column label="状态" width="110"><template #default="{row}"><StatusBadge :value="row.status"/></template></el-table-column>
            <el-table-column label="错误" min-width="180" show-overflow-tooltip><template #default="{row}"><span class="err-text">{{ row.error_message || '-' }}</span></template></el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane name="artifacts">
          <template #label>报告与附件 <span class="tab-count">{{ artifacts.length }}</span></template>
          <el-table :data="artifacts">
            <el-table-column prop="artifact_type" label="类型" width="130"/>
            <el-table-column prop="object_key" label="文件路径" min-width="320" show-overflow-tooltip><template #default="{row}"><span class="path">{{ row.object_key }}</span></template></el-table-column>
            <el-table-column label="大小" width="110"><template #default="{row}">{{ (row.size / 1024).toFixed(1) }} KB</template></el-table-column>
            <el-table-column label="操作" width="170">
              <template #default="{row}">
                <el-button v-if="isPreviewable(row)" link type="primary" @click="openPreview(row)">在线预览</el-button>
                <el-button link @click="download(`/tasks/${id}/artifacts/${row.id}/download`, row.object_key.split('/').pop())">下载</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog :model-value="preview.visible" :title="preview.name" width="86%" top="4vh" append-to-body @close="closePreview">
      <iframe v-if="preview.visible" :src="preview.url" class="preview-frame" sandbox="allow-same-origin"/>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-head h2 { margin: 8px 0 0; display: flex; gap: 12px; align-items: center; }
.overview { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 16px; }
.overview > div { position: relative; overflow: hidden; padding: 15px 16px; border: 1px solid var(--border-color); border-radius: 12px; background: var(--surface); box-shadow: var(--shadow-soft); }
.overview > div::after { content: ""; position: absolute; right: 0; bottom: 0; width: 35px; height: 1px; background: var(--primary); }
.overview span { color: var(--text-muted); font-size: 12px; }
.overview b { display: block; margin-top: 7px; color: var(--text-primary); font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tabs { margin-top: 16px; }
.tab-count { margin-left: 5px; padding: 1px 7px; border-radius: 10px; background: var(--primary-glow); color: var(--primary); font-size: 11px; font-weight: 700; }
.stream-state { display: flex; align-items: center; gap: 7px; margin-bottom: 10px; color: var(--text-muted); font-size: 12px; }
.stream-state i { width: 7px; height: 7px; border-radius: 50%; background: var(--text-muted); }
.stream-state.connected { color: var(--success); }
.stream-state.connected i { background: var(--success); box-shadow: 0 0 7px var(--success); }
.stream-state.fallback, .stream-state.reconnecting { color: var(--warning); }
.stream-state.fallback i, .stream-state.reconnecting i { background: var(--warning); box-shadow: 0 0 7px var(--warning); }
.result-tools { display: flex; flex-direction: column; gap: 12px; margin-bottom: 14px; }
.result-filter { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.path { font-family: Consolas, monospace; font-size: 12px; }
.err-text { color: var(--danger); font-size: 12px; }
.error-detail { padding: 10px 16px; }
.error-detail b { display: block; margin-bottom: 6px; color: var(--danger); font-size: 12px; }
.error-detail pre { margin: 0; padding: 12px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--surface-soft); color: var(--text-secondary); font: 12px/1.6 Consolas, monospace; white-space: pre-wrap; word-break: break-all; }
.preview-frame { width: 100%; height: 72vh; border: 1px solid var(--border-color); border-radius: 10px; background: #fff; }
</style>
