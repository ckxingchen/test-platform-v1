<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { auth } from '@/platform/auth/session'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import StatBar from '@/shared/components/StatBar.vue'

const router = useRouter()
const stats = reactive({ projects: 0, tasks: 0, running: 0, success: 0 })
const tasks = ref([]), projects = ref([]), projectMap = ref({})

const canWrite = computed(() => auth.user?.role !== 'viewer')

const segments = computed(() => {
  const count = { running: 0, queued: 0, success: 0, failed: 0, canceled: 0, timeout: 0 }
  for (const row of tasks.value) {
    if (row.status === 'dispatching') count.running++
    else if (count[row.status] !== undefined) count[row.status]++
  }
  return [
    { key: 'success', label: '成功', count: count.success, tone: 'success', main: true },
    { key: 'failed', label: '失败', count: count.failed + count.timeout, tone: 'danger' },
    { key: 'running', label: '进行中', count: count.running, tone: 'info' },
    { key: 'queued', label: '排队中', count: count.queued, tone: 'warning' },
    { key: 'canceled', label: '已取消', count: count.canceled, tone: 'muted' }
  ]
})
const recent = computed(() => [...tasks.value].sort((a, b) => b.id - a.id).slice(0, 6))

// 快速开始三步引导：承载「测试项目 → 执行器 → 任务」主线
const quickSteps = [
  { no: '01', title: '创建测试项目', desc: '新建测试项目，管理项目文件与用例', btn: '创建测试项目', path: '/objects/projects' },
  { no: '02', title: '配置执行器', desc: '配置执行器并部署测试框架', btn: '配置执行器', path: '/executors' },
  { no: '03', title: '发起任务', desc: '选择测试项目与执行器，发起运行任务', btn: '发起任务', path: '/tasks/create' }
]

function duration(row) {
  if (!row.started_at) return '-'
  const end = row.finished_at ? new Date(row.finished_at) : new Date()
  const sec = Math.max(0, Math.round((end - new Date(row.started_at)) / 1000))
  return sec < 60 ? `${sec}秒` : sec < 3600 ? `${Math.floor(sec / 60)}分${sec % 60}秒` : `${Math.floor(sec / 3600)}时${Math.floor((sec % 3600) / 60)}分`
}

onMounted(async () => {
  const [p, t] = await Promise.all([api.get('/objects/projects'), api.get('/tasks')])
  tasks.value = t.data
  projects.value = p.data
  projectMap.value = Object.fromEntries(p.data.map(x => [x.id, x.name]))
  stats.projects = p.data.length
  stats.tasks = t.data.length
  stats.running = t.data.filter(x => ['queued', 'dispatching', 'running'].includes(x.status)).length
  stats.success = t.data.filter(x => x.status === 'success').length
})
</script>

<template>
  <div class="page dashboard-page">
    <div class="page-head"><div><h2>仪表盘</h2><div class="muted">测试项目、执行器与任务运行态势</div></div><span class="sync"><i/> DATA SYNCED</span></div>

    <div class="grid">
      <div class="metric cyan"><span class="metric-label"><i/>项目数量</span><b>{{ stats.projects }}</b><small>ACTIVE PROJECTS</small></div>
      <div class="metric violet"><span class="metric-label"><i/>任务总数</span><b>{{ stats.tasks }}</b><small>TOTAL TASKS</small></div>
      <div class="metric amber"><span class="metric-label"><i/>执行中</span><b>{{ stats.running }}</b><small>IN PROGRESS</small></div>
      <div class="metric green"><span class="metric-label"><i/>成功任务</span><b>{{ stats.success }}</b><small>COMPLETED</small></div>
    </div>

    <div class="card steps-card">
      <h3>快速开始</h3>
      <div class="quick-steps">
        <div v-for="s in quickSteps" :key="s.no" class="quick-step">
          <span class="step-no">{{ s.no }}</span>
          <div class="step-body"><b>{{ s.title }}</b><p>{{ s.desc }}</p></div>
          <el-button size="small" type="primary" plain @click="router.push(s.no === '03' && !canWrite ? '/tasks' : s.path)">{{ s.no === '03' && !canWrite ? '查看任务' : s.btn }}</el-button>
        </div>
      </div>
    </div>

    <div class="row">
      <div class="card dist">
        <h3>任务状态分布</h3>
        <StatBar :segments="segments"/>
      </div>
      <div class="card recent">
        <div class="recent-head"><h3>最近任务</h3><el-button link type="primary" @click="router.push('/tasks')">查看全部 →</el-button></div>
        <div v-for="row in recent" :key="row.id" class="task-row" @click="router.push(`/tasks/${row.id}`)">
          <span class="tid">#{{ row.id }}</span>
          <span class="tname">{{ row.project_name || projectMap[row.project_id] || `项目 ${row.project_id}` }}</span>
          <StatusBadge :value="row.status"/>
          <span class="tdur">{{ duration(row) }}</span>
        </div>
        <div v-if="!recent.length" class="muted empty">暂无任务，去「任务」创建第一个任务吧</div>
      </div>
    </div>

  </div>
</template>

<style scoped>
.dashboard-page{height:calc(100vh - 76px);min-height:0;padding:20px 24px;overflow:hidden;display:grid;grid-template-rows:repeat(4,auto);align-content:start;gap:14px}
.dashboard-page .page-head{min-height:40px;margin:0}.page-head>div .muted{margin:5px 0 0 14px}.sync{display:flex;align-items:center;gap:7px;color:var(--success);font:700 9px/1 Inter,sans-serif;letter-spacing:.12em}.sync i{width:6px;height:6px;border-radius:50%;background:var(--success);box-shadow:0 0 9px var(--success)}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:0}.metric{position:relative;overflow:hidden;padding:16px 18px;border:1px solid var(--border-color);border-radius:14px;background:var(--surface);box-shadow:var(--shadow-soft);transition:.25s ease}.metric::after{content:"";position:absolute;right:-20px;bottom:-28px;width:92px;height:92px;border:1px solid currentColor;border-radius:50%;opacity:.1}.metric:hover{transform:translateY(-2px);border-color:currentColor}.metric-label{display:flex;align-items:center;gap:8px;color:var(--text-secondary);font-size:12px}.metric-label i{width:6px;height:6px;border-radius:2px;background:currentColor;box-shadow:0 0 8px currentColor}.metric b{display:block;margin-top:10px;color:var(--text-primary);font-size:27px;line-height:1}.metric small{display:block;margin-top:8px;color:var(--text-muted);font:600 8px/1 Inter,sans-serif;letter-spacing:.13em}.metric.cyan{color:var(--primary)}.metric.violet{color:var(--accent)}.metric.amber{color:var(--warning)}.metric.green{color:var(--success)}
.steps-card{margin:0;padding:15px 17px}.steps-card h3{margin:0 0 11px;font-size:15px}.quick-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.quick-step{display:flex;align-items:center;gap:11px;min-width:0;padding:11px 12px;border:1px solid var(--border-color);border-radius:12px;background:var(--surface-soft)}.step-no{flex:0 0 auto;width:34px;height:34px;display:grid;place-items:center;border:1px solid var(--border-strong);border-radius:9px;color:var(--primary);background:var(--primary-glow);font:800 11px/1 Inter,sans-serif}.step-body{flex:1;min-width:0}.step-body b{display:block;overflow:hidden;color:var(--text-primary);font-size:13px;text-overflow:ellipsis;white-space:nowrap}.step-body p{margin:3px 0 0;overflow:hidden;color:var(--text-muted);font-size:11px;line-height:1.35;text-overflow:ellipsis;white-space:nowrap}
.row{min-height:0;display:grid;grid-template-columns:minmax(280px,.85fr) minmax(0,1.45fr);align-items:stretch;gap:14px;margin:0}.dist,.recent{min-height:0;overflow:hidden;padding:16px 18px}.dist h3,.recent h3{margin:0 0 12px;font-size:15px}.recent-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}.task-row{display:flex;align-items:center;gap:12px;padding:7px 9px;border-radius:9px;cursor:pointer;transition:.15s}.task-row:hover{background:var(--surface-hover)}.task-row .tid{color:var(--text-muted);font:700 12px Consolas,monospace;flex:0 0 52px}.task-row .tname{flex:1;color:var(--text-primary);font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.task-row .tdur{color:var(--text-muted);font-size:11.5px;flex:0 0 76px;text-align:right}.empty{padding:20px;text-align:center}
@media(max-width:1250px){.step-body p{display:none}.quick-step{gap:9px}.row{grid-template-columns:minmax(250px,.75fr) minmax(0,1.45fr)}}
@media(max-height:760px){.dashboard-page{padding:14px 18px;gap:10px}.dashboard-page .page-head{min-height:36px}.grid{gap:10px}.metric{padding:12px 15px}.metric b{margin-top:7px;font-size:24px}.metric small{margin-top:6px}.steps-card{padding:11px 14px}.steps-card h3{margin-bottom:8px}.quick-step{padding:8px 10px}.step-body p{display:none}.dist,.recent{padding:12px 15px}.dist h3,.recent h3{margin-bottom:8px}.task-row{padding:5px 8px}}
</style>
