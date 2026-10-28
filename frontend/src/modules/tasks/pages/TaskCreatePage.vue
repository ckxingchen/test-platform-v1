<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { TERM } from '@/shared/constants/terminology'
import IniEditor from '@/shared/components/IniEditor.vue'
import CaseCheckTree from '@/shared/components/CaseCheckTree.vue'

const router = useRouter(), route = useRoute()
const projects = ref([]), environments = ref([]), files = ref([]), loading = ref(false), loadingFiles = ref(false)
const configDialog = ref(false)
const form = reactive({ project_id: null, environment_id: null, selected_case_paths: [], config_content: '', timeout_seconds: 3600 })
const cloneFrom = ref(null)

// 配置摘要：统计配置节数与参数数，展示在按钮旁
const configSummary = computed(() => {
  const text = form.config_content || ''
  if (!text.trim()) return '尚未载入配置（选择项目后自动读取）'
  const sections = [...text.matchAll(/^\s*\[(.+?)\]\s*$/gm)].length
  const params = [...text.matchAll(/^[^;#\[][^=\n]*=/gm)].length
  return `已载入 ${sections} 个配置节 · ${params} 个参数`
})

const DEPLOY_LABELS = { deployed: '已部署', deploying: '部署中', pending: '待部署', not_deployed: '未部署', failed: '部署失败' }

// 用例树：仅展示 testcase/ 目录下的用例文件（组件内部已隐藏 casedata 与前后置 yml）
const casePaths = computed(() => files.value.map(x => x.relative_path).filter(p => p.startsWith('testcase/')))
const selectedCount = computed(() => form.selected_case_paths.length)

const selectedEnv = computed(() => environments.value.find(e => e.id === form.environment_id))
function deployLabel(status) { return DEPLOY_LABELS[status] || status || '-' }
function shortSha(sha) { return sha ? sha.slice(0, 8) : '' }
function executorLabel(e) {
  const os = e.framework_os || e.os || '-'
  const arch = e.framework_arch || e.arch || '-'
  const state = e.ready ? 'READY' : (DEPLOY_LABELS[e.framework_status] || e.agent_status)
  return `${e.name} / ${e.framework_name || '-'}(${os}-${arch}) / ${state}`
}

const DEFAULT_INI = '[项目运行设置]\nreport_type = html\nparallel_workers = 1\n'

async function loadProject() {
  files.value = []
  form.selected_case_paths = []
  if (!form.project_id) { form.config_content = ''; return }
  loadingFiles.value = true
  try {
    files.value = (await api.get(`/objects/projects/${form.project_id}/files`)).data
    if (!files.value.length) {
      form.config_content = DEFAULT_INI
      ElMessage.warning('该项目还没有上传任何文件，已填入默认配置')
      return
    }
    // 自动定位默认 ini：优先 config/配置文件.ini，否则取 config/ 目录下第一个 ini 文件
    const config = files.value.find(x => x.relative_path === 'config/配置文件.ini')
      || files.value.find(x => x.relative_path.startsWith('config/') && x.relative_path.toLowerCase().endsWith('.ini'))
    if (config) {
      try {
        const response = await api.get(`/objects/projects/${form.project_id}/files/${config.id}/download`, { responseType: 'blob' })
        form.config_content = await response.data.text()
        ElMessage.success(`已载入默认配置 ${config.relative_path}`)
      } catch {
        form.config_content = DEFAULT_INI
        ElMessage.error('默认配置文件下载失败，已填入默认配置')
      }
    } else {
      form.config_content = DEFAULT_INI
      ElMessage.info('项目 config/ 目录下未找到 ini 文件，已填入默认配置')
    }
  } finally { loadingFiles.value = false }
}

async function submit() {
  loading.value = true
  try {
    const payload = {
      project_id: form.project_id,
      environment_id: form.environment_id,
      selected_case_paths: form.selected_case_paths.length ? form.selected_case_paths : null,
      config_content: form.config_content,
      timeout_seconds: form.timeout_seconds,
    }
    const task = (await api.post('/tasks', payload)).data
    ElMessage.success('任务已创建')
    router.push(`/tasks/${task.id}`)
  } finally { loading.value = false }
}

onMounted(async () => {
  const [p, e] = await Promise.all([api.get('/objects/projects'), api.get('/environments')])
  projects.value = p.data
  environments.value = e.data.filter(x => x.enabled)
  // 支持两种入口：?project=<id> 直接指定项目；?clone=<taskId> 克隆已有任务
  if (route.query.clone) {
    try {
      const old = (await api.get(`/tasks/${route.query.clone}`)).data
      cloneFrom.value = old
      form.project_id = old.project_id
      form.environment_id = old.environment_id
      form.selected_case_paths = old.selected_case_paths || []
      form.timeout_seconds = old.timeout_seconds || 3600
      ElMessage.info(`已克隆任务 #${old.id} 的配置，配置文件已载入项目当前默认版本`)
    } catch { /* 拦截器已提示 */ }
  } else if (route.query.project) {
    form.project_id = Number(route.query.project)
  }
  if (form.project_id) await loadProject()
})
watch(() => form.project_id, (next, prev) => {
  if (next !== prev) {
    if (!cloneFrom.value) form.selected_case_paths = []
    loadProject()
    cloneFrom.value = null
  }
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div><h2>新建任务</h2><div class="muted">先选择{{ TERM.project }}，再选择{{ TERM.executor }}（已部署到最新状态），然后配置运行参数与勾选用例</div></div>
    </div>
    <div class="layout">
      <div class="card form">
        <el-form label-position="top">
          <el-form-item :label="'① ' + TERM.project">
            <el-select v-model="form.project_id" filterable placeholder="选择测试项目" style="width:100%">
              <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id"/>
            </el-select>
          </el-form-item>
          <el-form-item :label="'② ' + TERM.executor">
            <el-select v-model="form.environment_id" filterable placeholder="选择执行器（仅显示 READY）" style="width:100%">
              <el-option v-for="e in environments" :key="e.id" :label="executorLabel(e)" :value="e.id" :disabled="!e.ready"/>
            </el-select>
            <div v-if="selectedEnv" class="executor-hint">
              已部署框架：<b>{{ selectedEnv.framework_name || '-' }}</b>（{{ selectedEnv.framework_os || '-' }}-{{ selectedEnv.framework_arch || '-' }}）
              · 部署状态：<b>{{ deployLabel(selectedEnv.framework_status) }}</b>
              <template v-if="selectedEnv.framework_sha256"> · 版本 <code>{{ shortSha(selectedEnv.framework_sha256) }}</code></template>
            </div>
          </el-form-item>
          <el-form-item label="超时（秒）">
            <el-input-number v-model="form.timeout_seconds" :min="10" :max="86400" style="width:100%"/>
          </el-form-item>
          <el-form-item label="本次运行配置文件.ini">
            <div class="config-entry">
              <el-button type="primary" plain :disabled="!form.project_id" @click="configDialog = true">
                查看并编辑运行配置
              </el-button>
              <span class="config-summary">{{ configSummary }}</span>
            </div>
          </el-form-item>
          <div class="muted">配置默认读取项目 config/ 目录下的 ini 文件；弹窗内仅可修改参数值，不能新增配置项；运行时在执行器生成新的配置文件，不修改项目默认文件。</div>
          <div class="actions">
            <el-button @click="router.back()">取消</el-button>
            <el-button type="primary" :loading="loading" :disabled="!form.project_id || !form.environment_id || !form.config_content" @click="submit">运行任务</el-button>
          </div>
        </el-form>
      </div>

      <div class="card picker">
        <div class="picker-head">
          <b>勾选用例</b>
          <span v-if="selectedCount" class="selected">已勾选 {{ selectedCount }} 项 <el-button link type="danger" @click="form.selected_case_paths = []">清除</el-button></span>
          <span v-else class="muted">{{ form.project_id ? '勾选目录或文件作为运行范围，留空运行整个项目' : '请先选择测试项目' }}</span>
        </div>
        <CaseCheckTree v-if="form.project_id" v-model="form.selected_case_paths" :paths="casePaths" :height="520"
                  empty-text="该项目 testcase/ 目录下暂无用例文件"/>
        <div v-else class="placeholder">选择项目后这里会显示 testcase/ 目录的用例树</div>
        <div v-if="loadingFiles" class="muted loading-tip">正在加载项目文件...</div>
      </div>
    </div>

    <el-dialog v-model="configDialog" title="本次运行配置文件.ini" width="960" append-to-body top="4vh" class="config-dialog">
      <div class="dialog-tip">参数名固定不可增删，仅可修改参数值；修改即时生效并写入本次任务运行配置。</div>
      <IniEditor v-model="form.config_content" :height="520"/>
      <template #footer>
        <el-button type="primary" @click="configDialog = false">完成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.layout { display: grid; grid-template-columns: minmax(520px, 1fr) 420px; gap: 16px; align-items: start; }
.form { max-width: none; }
.actions { text-align: right; margin-top: 18px; }
.picker { position: sticky; top: 20px; }
.picker-head { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.picker-head b { color: var(--text-primary); font-size: 14px; }
.picker-head .selected { color: var(--primary); font-size: 12px; font-family: Consolas, monospace; word-break: break-all; }
.placeholder { padding: 60px 20px; border: 1px dashed var(--border-color); border-radius: 10px; color: var(--text-muted); text-align: center; font-size: 13px; }
.loading-tip { margin-top: 8px; text-align: center; }
.executor-hint { margin-top: 8px; font-size: 12.5px; color: var(--text-secondary); line-height: 1.6; }
.executor-hint b { color: var(--primary); }
.executor-hint code { font-family: Consolas, monospace; color: var(--accent); background: var(--accent-glow); padding: 1px 5px; border-radius: 4px; }
.config-entry { display: flex; align-items: center; gap: 14px; width: 100%; }
.config-summary { color: var(--text-secondary); font-size: 12.5px; }
.dialog-tip { margin-bottom: 10px; color: var(--text-muted); font-size: 12.5px; }
.picker { position: sticky; top: 20px; max-height: calc(100vh - 200px); overflow-y: auto; padding-right: 4px; }
@media (max-width: 1400px) { .layout { grid-template-columns: 1fr; } .picker { position: static; } }
</style>
