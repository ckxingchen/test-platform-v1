<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { isAdmin, TERM } from '@/shared/constants/terminology'
import StatusBadge from '@/shared/components/StatusBadge.vue'

const router = useRouter()
const rows = ref([]), frameworks = ref([]), agentPackages = ref([])
const dialog = ref(false), deployAgentDialog = ref(false), deployDialog = ref(false), frameworkSelectDialog = ref(false)
const deployAgentResult = ref(null), deployAgentLoading = ref(false)
const deployments = ref([]), logs = ref([]), activeEnv = ref(null), activeDeployment = ref(null), timer = ref(null)
const testResult = ref(null), testing = ref(false)
const formRef = ref(null)
const form = reactive({
  id: null, name: '', host: '', ssh_port: 22, ssh_username: '', ssh_password: '',
  os: null, arch: null, agent_home: '/opt/kw-agent', max_workers: 1, enabled: true
})
const frameworkForm = reactive({ environment_id: null, framework_id: null })

const formRules = {
  name: [{ required: true, message: '请输入执行器名称', trigger: 'blur' }],
  host: [{ required: true, message: '请输入远程主机 IP', trigger: 'blur' }],
  ssh_username: [{ required: true, message: '请输入 SSH 用户名', trigger: 'blur' }],
  agent_home: [{ required: true, message: '请输入 Agent 安装目录', trigger: 'blur' }],
}

const saveDisabledReason = computed(() => {
  if (!form.name?.trim()) return '请填写执行器名称'
  if (!form.host?.trim()) return '请填写远程主机 IP'
  if (!form.ssh_username?.trim()) return '请填写 SSH 用户名'
  if (!form.id && !form.ssh_password) return '请填写 SSH 密码'
  return ''
})
const isSaveDisabled = computed(() => saveDisabledReason.value !== '')

async function load() {
  const [environments, frameworkObjects, packages] = await Promise.all([
    api.get('/environments'),
    api.get('/objects/frameworks'),
    api.get('/objects/agents')
  ])
  rows.value = environments.data
  frameworks.value = frameworkObjects.data
  agentPackages.value = packages.data
}

function open(row = null) {
  testResult.value = null
  Object.assign(form, row ? {
    id: row.id, name: row.name, host: row.host, ssh_port: row.ssh_port || 22,
    ssh_username: row.ssh_username || '', ssh_password: '',
    os: row.os, arch: row.arch, agent_home: row.agent_home, max_workers: row.max_workers || 1,
    enabled: row.enabled
  } : {
    id: null, name: '', host: '', ssh_port: 22, ssh_username: '', ssh_password: '',
    os: null, arch: null, agent_home: '/opt/kw-agent', max_workers: 1, enabled: true
  })
  dialog.value = true
  nextTick(() => formRef.value?.clearValidate())
}

async function testConnection() {
  testing.value = true
  testResult.value = null
  try {
    testResult.value = (await api.post('/environments/test-connection', {
      host: form.host, ssh_port: form.ssh_port, ssh_username: form.ssh_username, ssh_password: form.ssh_password
    })).data
    if (testResult.value.ok) {
      // 自动回填探测结果
      form.os = testResult.value.os
      form.arch = testResult.value.arch
      if (form.os === 'windows' && (form.agent_home === '/opt/kw-agent' || !form.agent_home)) form.agent_home = 'D:\\kw-agent'
      if (form.os === 'linux' && (form.agent_home === 'D:\\kw-agent' || !form.agent_home)) form.agent_home = '/opt/kw-agent'
    }
  } finally { testing.value = false }
}

async function save() {
  if (formRef.value) {
    const valid = await formRef.value.validate().catch(() => false)
    if (!valid) return
  }
  const data = {
    name: form.name, host: form.host, ssh_port: form.ssh_port, ssh_username: form.ssh_username,
    ssh_password: form.ssh_password || '', os: form.os, arch: form.arch,
    agent_home: form.agent_home, max_workers: form.max_workers, enabled: form.enabled
  }
  await api[form.id ? 'put' : 'post'](form.id ? `/environments/${form.id}` : '/environments', data)
  dialog.value = false; ElMessage.success('执行器已保存'); load()
}

async function deployAgent(row) {
  if (!row.os || !row.arch || !row.ssh_username) {
    ElMessage.warning('执行器尚未配置 SSH 凭据或 OS/架构，请先在「编辑执行器」中填写 SSH 用户名/密码并点击「测试连接」保存探测结果')
    return
  }
  const redeploy = row.agent_sha256
  if (redeploy && (row.running_tasks || 0) > 0) { ElMessage.warning('执行器存在运行中任务，禁止重新部署 Agent'); return }
  if (redeploy) await ElMessageBox.confirm(`重新部署会停止旧 Agent 并替换 bin/（config/data/logs 保留），确认继续？`, '重新部署 Agent', { type: 'warning' })
  activeEnv.value = row
  deployAgentResult.value = null
  deployAgentLoading.value = true
  deployAgentDialog.value = true
  try {
    deployAgentResult.value = (await api.post(`/environments/${row.id}/deploy-agent`)).data
    ElMessage[deployAgentResult.value.success ? 'success' : 'warning'](deployAgentResult.value.success ? 'Agent 部署成功，已上线' : '部署命令已执行，但未检测到心跳')
  } catch (e) {
    deployAgentResult.value = { success: false, steps: [e.response?.data?.detail || e.message], agent_status: row.agent_status, agent_sha256: null }
  } finally { deployAgentLoading.value = false; load() }
}

async function toggleAgent(row, action) {
  if (action === 'stop' && row.running_tasks > 0) { ElMessage.warning('执行器存在运行中任务，禁止停止 Agent'); return }
  await api.post(`/environments/${row.id}/${action}-agent`)
  ElMessage.success(action === 'start' ? 'Agent 启动命令已执行' : 'Agent 已停止')
  load()
}

function openFrameworkSelect(row) {
  if (row.agent_status !== 'online') {
    ElMessage.warning('请先部署并上线 Agent，再部署测试框架')
    return
  }
  if (row.framework_status === 'deploying') {
    ElMessage.warning('框架正在部署中，请稍候')
    return
  }
  if ((row.running_tasks || 0) > 0) {
    ElMessage.warning('执行器存在运行中任务，暂不能部署框架')
    return
  }
  frameworkForm.environment_id = row.id
  frameworkForm.framework_id = row.framework_id || null
  frameworkSelectDialog.value = true
}

const selectableFrameworks = computed(() => {
  const env = rows.value.find(x => x.id === frameworkForm.environment_id)
  if (!env) return frameworks.value
  return frameworks.value.filter(f => (!env.os || !f.os || f.os === env.os) && (!env.arch || !f.arch || f.arch === env.arch))
})

async function deployFrameworkSubmit() {
  if (!frameworkForm.framework_id) { ElMessage.warning('请选择测试框架'); return }
  try {
    await api.post(`/environments/${frameworkForm.environment_id}/deploy`, { framework_id: frameworkForm.framework_id })
    ElMessage.success('框架部署请求已下发，等待 Agent 拉取')
    frameworkSelectDialog.value = false
    load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '下发失败')
  }
}

async function showDeployments(row) {
  activeEnv.value = row; activeDeployment.value = null; logs.value = []
  await loadDeployments()
  if (deployments.value.length) { activeDeployment.value = deployments.value[0]; await loadDeployments() }
  deployDialog.value = true
}

async function loadDeployments() {
  deployments.value = (await api.get(`/environments/${activeEnv.value.id}/deployments`)).data
  if (activeDeployment.value) {
    activeDeployment.value = deployments.value.find(x => x.id === activeDeployment.value.id) || activeDeployment.value
    logs.value = (await api.get(`/environments/${activeEnv.value.id}/deployments/${activeDeployment.value.id}/logs`)).data.logs
  }
}

async function pollDeploy() {
  clearTimeout(timer.value)
  await Promise.all([load(), loadDeployments()])
  if (['queued', 'running'].includes(activeDeployment.value?.status)) timer.value = setTimeout(pollDeploy, 1800)
}

async function selectDeployment(row) {
  activeDeployment.value = row
  logs.value = (await api.get(`/environments/${activeEnv.value.id}/deployments/${row.id}/logs`)).data.logs
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除执行器 ${row.name}？`)
  await api.delete(`/environments/${row.id}`)
  load()
}

const AGENT_LABELS = { pending: '未部署', online: '在线', offline: '离线', deploying: '部署中' }
const FRAMEWORK_LABELS = { not_deployed: '未部署', pending: '待部署', deploying: '部署中', deployed: '已部署', failed: '失败' }
function agentLabel(row) {
  if (row.agent_update_available) return '待重新部署'
  return AGENT_LABELS[row.agent_status] || row.agent_status
}
function frameworkLabel(row) {
  if (row.framework_update_available) return '待重新部署'
  return FRAMEWORK_LABELS[row.framework_status] || row.framework_status
}
function runLabel(row) {
  if (row.agent_status !== 'online') return '不可用'
  return (row.active_task_count || 0) >= (row.max_workers || 1) ? '忙碌' : '空闲'
}
function agentTagType(row) {
  if (row.agent_update_available) return 'warning'
  return { online: 'success', offline: 'info', pending: 'info', deploying: '' }[row.agent_status] || 'info'
}
function frameworkTagType(row) {
  if (row.framework_update_available) return 'warning'
  return { deployed: 'success', deploying: '', pending: '', not_deployed: 'info', failed: 'danger' }[row.framework_status] || 'info'
}
function runTagType(row) {
  if (row.agent_status !== 'online') return 'info'
  return (row.active_task_count || 0) >= (row.max_workers || 1) ? 'danger' : 'success'
}

const stats = computed(() => {
  const list = rows.value
  return {
    total: list.length,
    ready: list.filter(x => x.ready).length,
    online: list.filter(x => x.agent_status === 'online').length,
    busy: list.filter(x => runLabel(x) === '忙碌').length,
    concurrency: list.filter(x => x.agent_status === 'online').reduce((s, x) => s + (x.max_workers || 0), 0)
  }
})
onMounted(load)
onBeforeUnmount(() => clearTimeout(timer.value))
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div><h2>{{ TERM.executor }}</h2><div class="muted">填写 SSH 信息创建执行器 → 测试连接 → 部署 Agent → 部署框架 → READY 后可执行任务</div></div>
      <el-button v-if="isAdmin()" type="primary" @click="open()">新建执行器</el-button>
    </div>
    <div class="stat-cards">
      <div class="stat-card cyan"><span>执行器总数</span><b>{{ stats.total }}</b><small>EXECUTORS</small></div>
      <div class="stat-card green"><span>READY</span><b>{{ stats.ready }}</b><small>READY</small></div>
      <div class="stat-card violet"><span>Agent 在线</span><b>{{ stats.online }}</b><small>ONLINE</small></div>
      <div class="stat-card red"><span>忙碌</span><b>{{ stats.busy }}</b><small>BUSY</small></div>
      <div class="stat-card amber"><span>在线总并发</span><b>{{ stats.concurrency }}</b><small>CONCURRENCY</small></div>
    </div>
    <div class="card filters">
      <span class="muted">共 {{ rows.length }} 个执行器</span>
    </div>
    <div class="card"><el-table :data="rows">
      <el-table-column label="执行器名称" min-width="130"><template #default="{row}"><el-link type="primary" @click="router.push(`/executors/${row.id}`)">{{ row.name }}</el-link></template></el-table-column>
      <el-table-column label="SSH 主机" min-width="150"><template #default="{row}">{{ row.host }}:{{ row.ssh_port }}</template></el-table-column>
      <el-table-column label="平台" min-width="105"><template #default="{row}">{{ row.os || '-' }} / {{ row.arch || '-' }}</template></el-table-column>
      <el-table-column label="Agent" width="105"><template #default="{row}"><el-tag size="small" :type="agentTagType(row)">{{ agentLabel(row) }}</el-tag></template></el-table-column>
      <el-table-column label="框架" width="105"><template #default="{row}"><el-tag size="small" :type="frameworkTagType(row)">{{ frameworkLabel(row) }}</el-tag></template></el-table-column>
      <el-table-column label="运行" width="80"><template #default="{row}"><el-tag size="small" :type="runTagType(row)">{{ runLabel(row) }}</el-tag></template></el-table-column>
      <el-table-column label="并发" width="75"><template #default="{row}">{{ row.active_task_count ?? 0 }}/{{ row.max_workers }}</template></el-table-column>
      <el-table-column label="测试框架" min-width="120"><template #default="{row}">{{ row.framework_name || '-' }}</template></el-table-column>
      <el-table-column label="归属人" min-width="100"><template #default="{row}">{{ row.owner_name || '-' }}</template></el-table-column>
      <el-table-column label="操作" :width="isAdmin() ? 380 : 60" fixed="right">
        <template #default="{row}">
          <el-button link type="primary" @click="router.push(`/executors/${row.id}`)">详情</el-button>
          <template v-if="isAdmin()">
            <el-button link type="primary" @click="open(row)">编辑</el-button>
            <el-button link type="primary" @click="deployAgent(row)">{{ row.agent_sha256 ? '重新部署Agent' : '部署Agent' }}</el-button>
            <el-button link type="primary" @click="openFrameworkSelect(row)">{{ row.framework_sha256 ? '重新部署框架' : '部署框架' }}</el-button>
            <el-button v-if="row.agent_status === 'online'" link type="warning" @click="toggleAgent(row, 'stop')">停止</el-button>
            <el-button v-else-if="row.agent_sha256" link type="success" @click="toggleAgent(row, 'start')">启动</el-button>
          </template>
        </template>
      </el-table-column>
      <template #empty><el-empty description="暂无执行器，点击右上角「新建执行器」开始"/></template>
    </el-table></div>

    <el-dialog v-model="dialog" :title="form.id ? '编辑执行器' : '新建执行器'" width="680" append-to-body>
      <el-alert type="info" :closable="false" class="guide-alert" title="平台通过 SSH 自动部署 Agent（SFTP 上传 + 远程启动），目标主机需开启 SSH（Windows 需 OpenSSH Server）"/>
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top">
        <el-row :gutter="14">
          <el-col :span="12"><el-form-item label="执行器名称" prop="name"><el-input v-model="form.name" placeholder="win-agent-01"/></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="远程主机 IP" prop="host"><el-input v-model="form.host" placeholder="192.168.1.20"/></el-form-item></el-col>
        </el-row>
        <el-row :gutter="14">
          <el-col :span="6"><el-form-item label="SSH 端口"><el-input-number v-model="form.ssh_port" :min="1" :max="65535" style="width:100%"/></el-form-item></el-col>
          <el-col :span="9"><el-form-item label="SSH 用户名" prop="ssh_username"><el-input v-model="form.ssh_username" placeholder="root / administrator"/></el-form-item></el-col>
          <el-col :span="9"><el-form-item :label="form.id ? 'SSH 密码（留空不修改）' : 'SSH 密码'" :required="!form.id"><el-input v-model="form.ssh_password" type="password" show-password placeholder="加密存储"/></el-form-item></el-col>
        </el-row>
        <el-form-item>
          <el-button :loading="testing" @click="testConnection">测试连接</el-button>
          <span v-if="testResult" :style="{ marginLeft: '12px', color: testResult.ok ? 'var(--success)' : 'var(--danger)', fontSize: '12.5px' }">
            {{ testResult.message }}
          </span>
          <span v-else class="muted" style="margin-left:12px;font-size:12.5px">测试连接会自动探测 OS / 架构并回填</span>
        </el-form-item>
        <el-row :gutter="14">
          <el-col :span="14"><el-form-item label="Agent 安装目录" prop="agent_home"><el-input v-model="form.agent_home" placeholder="Linux: /opt/kw-agent；Windows: D:\kw-agent"/></el-form-item></el-col>
          <el-col :span="10"><el-form-item label="最大并发任务数"><el-input-number v-model="form.max_workers" :min="1" :max="100" style="width:100%"/></el-form-item></el-col>
        </el-row>
        <el-form-item label="探测结果（OS / 架构）">
          <el-tag v-if="form.os" size="small">{{ form.os }} / {{ form.arch }}</el-tag>
          <span v-else class="muted" style="font-size:12.5px">未探测（保存后仍可部署 Agent，但需要先测试连接）</span>
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled"/></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-tooltip :disabled="!isSaveDisabled" :content="saveDisabledReason" placement="top">
          <span><el-button type="primary" :disabled="isSaveDisabled" @click="save">保存</el-button></span>
        </el-tooltip>
      </template>
    </el-dialog>

    <el-dialog v-model="deployAgentDialog" title="部署 Agent" width="620" append-to-body :close-on-click-modal="false">
      <div v-loading="deployAgentLoading" element-loading-text="正在通过 SSH 部署 Agent，请稍候…">
        <template v-if="deployAgentResult">
          <el-alert :type="deployAgentResult.success ? 'success' : 'warning'" :closable="false" style="margin-bottom:14px"
            :title="deployAgentResult.success ? 'Agent 已上线' : '部署未完全成功，请检查步骤日志'"/>
          <div class="deploy-steps">
            <div v-for="(step, i) in deployAgentResult.steps" :key="i" class="deploy-step">
              <span class="step-index">{{ i + 1 }}</span><span>{{ step }}</span>
            </div>
          </div>
        </template>
      </div>
      <template #footer><el-button type="primary" @click="deployAgentDialog = false">关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="frameworkSelectDialog" title="部署测试框架" width="520" append-to-body>
      <el-alert type="info" :closable="false" class="guide-alert" title="选择与执行器 OS / 架构匹配的框架，Agent 会自动拉取并部署到固定目录"/>
      <el-form label-position="top">
        <el-form-item label="测试框架" required>
          <el-select v-model="frameworkForm.framework_id" filterable style="width:100%" placeholder="选择框架">
            <el-option v-for="f in selectableFrameworks" :key="f.id" :label="`${f.name} (${f.os}-${f.arch})`" :value="f.id"/>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="frameworkSelectDialog = false">取消</el-button>
        <el-button type="primary" @click="deployFrameworkSubmit">下发部署</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="deployDialog" :title="`部署历史 - ${activeEnv?.name || ''}`" width="760" append-to-body @opened="pollDeploy">
      <el-table :data="deployments" highlight-current-row @current-change="selectDeployment" size="small">
        <el-table-column prop="id" label="#" width="60"/>
        <el-table-column label="SHA256" width="140"><template #default="{row}"><code class="sha">{{ row.framework_sha256?.slice(0, 12) }}…</code></template></el-table-column>
        <el-table-column prop="status" label="状态" width="90"><template #default="{row}"><StatusBadge :value="row.status"/></template></el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="150"><template #default="{row}">{{ new Date(row.created_at).toLocaleString() }}</template></el-table-column>
        <el-table-column prop="finished_at" label="完成时间" min-width="150"><template #default="{row}">{{ row.finished_at ? new Date(row.finished_at).toLocaleString() : '-' }}</template></el-table-column>
      </el-table>
      <div class="deploy-logs"><div v-for="(log, i) in logs" :key="i" class="log-line" :class="{ error: log.level === 'ERROR' }">[{{ log.level }}] {{ log.message }}</div><div v-if="!logs.length" class="muted" style="padding:12px">暂无日志</div></div>
      <template #footer><el-button @click="deployDialog = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.sha { font-family: Consolas, monospace; font-size: 12px; }
.guide-alert { margin-bottom: 16px; }
.deploy-steps { max-height: 320px; overflow-y: auto; }
.deploy-step { display: flex; gap: 10px; padding: 7px 0; border-bottom: 1px dashed var(--border-color); font-size: 13px; }
.step-index { flex: none; width: 20px; height: 20px; display: grid; place-items: center; border-radius: 50%; background: var(--primary-glow); color: var(--primary); font-size: 11px; }
.deploy-logs { margin-top: 12px; max-height: 260px; overflow-y: auto; background: var(--surface-soft); border-radius: 8px; padding: 10px; font-family: Consolas, monospace; font-size: 12px; }
.log-line { padding: 2px 0; white-space: pre-wrap; word-break: break-all; }
.log-line.error { color: var(--danger); }
.stat-cards { display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; margin-bottom: 16px; }
.stat-card { position: relative; overflow: hidden; padding: 17px 18px; border: 1px solid var(--border-color); border-radius: 12px; background: var(--surface); box-shadow: var(--shadow-soft); transition: .25s ease; }
.stat-card:hover { transform: translateY(-2px); border-color: currentColor; }
.stat-card span { color: var(--text-secondary); font-size: 12px; }
.stat-card b { display: block; margin-top: 9px; color: var(--text-primary); font-size: 26px; line-height: 1; }
.stat-card small { display: block; margin-top: 8px; color: var(--text-muted); font: 600 8px/1 Inter, sans-serif; letter-spacing: .13em; }
.stat-card.cyan { color: var(--primary); }
.stat-card.green { color: var(--success); }
.stat-card.red { color: var(--danger); }
.stat-card.violet { color: var(--accent); }
.stat-card.amber { color: var(--warning); }
@media (max-width: 1100px) { .stat-cards { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 760px) { .stat-cards { grid-template-columns: repeat(2, 1fr); } }
</style>
