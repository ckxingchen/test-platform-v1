<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, download } from '../api'
import { auth } from '@/platform/auth/session'
import CodeEditor from '@/shared/components/CodeEditor.vue'
import PathTree from '@/shared/components/PathTree.vue'
import CaseCheckTree from '@/shared/components/CaseCheckTree.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'

const route = useRoute(), router = useRouter(), id = route.params.id
const project = ref({}), files = ref([]), users = ref([]), members = ref([]), tasks = ref([])
const activeTab = ref('files')
const uploadDialog = ref(false), editorDialog = ref(false), memberDialog = ref(false)
const edit = reactive({ id: null, path: '', content: '' })
const selectedDir = ref(''), search = ref('')
// 上传方式：full = 整个项目目录全量上传；partial = 勾选部分上传
const uploadMode = ref('full')
// 选中的本地文件：pickedFiles 存 { file, path }（path 已剥离根目录名）
const pickedFiles = ref([]), uploading = ref(false), projectRootName = ref('')
// 部分上传：checkedPaths 为已勾选路径集合
const checkedPaths = ref([])
const treeRelativePaths = computed(() => pickedFiles.value.map(x => x.path))

const canWrite = computed(() => auth.user?.role === 'admin' || members.value.some(x => x.user_id === auth.user?.id && x.role === 'developer'))
const EDITABLE = /\.(ini|ya?ml|json|py|txt|md|csv|sh|xml)$/i
const allPaths = computed(() => files.value.map(x => x.relative_path))

const visibleFiles = computed(() => files.value.filter(row => {
  if (selectedDir.value && !row.relative_path.startsWith(selectedDir.value + '/')) return false
  if (search.value && !row.relative_path.toLowerCase().includes(search.value.toLowerCase())) return false
  return true
}))

function langOf(path) {
  if (/\.ini$/i.test(path)) return 'ini'
  if (/\.ya?ml$/i.test(path)) return 'yaml'
  if (/\.json$/i.test(path)) return 'json'
  if (/\.py$/i.test(path)) return 'python'
  return 'text'
}

async function load() {
  const [p, fs, ms] = await Promise.all([
    api.get(`/objects/projects/${id}`), api.get(`/objects/projects/${id}/files`), api.get(`/objects/projects/${id}/members`)
  ])
  project.value = p.data; files.value = fs.data; members.value = ms.data
  if (auth.user?.role === 'admin') users.value = (await api.get('/users')).data
}

async function loadTasks() { tasks.value = (await api.get(`/objects/projects/${id}/tasks`)).data }

function taskDuration(row) {
  if (!row.started_at) return '-'
  const end = row.finished_at ? new Date(row.finished_at) : new Date()
  const sec = Math.max(0, Math.round((end - new Date(row.started_at)) / 1000))
  if (sec < 60) return `${sec} 秒`
  if (sec < 3600) return `${Math.floor(sec / 60)} 分 ${sec % 60} 秒`
  return `${Math.floor(sec / 3600)} 时 ${Math.floor((sec % 3600) / 60)} 分`
}

function onTabChange(name) { if (name === 'tasks' && !tasks.value.length) loadTasks() }

function onTreeSelect(row) {
  if (row.isDir) {
    selectedDir.value = selectedDir.value === row.path ? '' : row.path
  } else {
    const file = files.value.find(x => x.relative_path === row.path)
    if (file && EDITABLE.test(file.relative_path)) openEdit(file)
  }
}

function choose(event) {
  // 选择文件夹后读取 webkitRelativePath 剥离根目录名
  const list = [...event.target.files]
  pickedFiles.value = list.map(f => {
    const rel = (f.webkitRelativePath || f.name).replaceAll('\\', '/')
    const parts = rel.split('/')
    const path = parts.length > 1 ? parts.slice(1).join('/') : rel
    return { file: f, path }
  })
  checkedPaths.value = pickedFiles.value.map(x => x.path) // 部分上传：默认全选
  projectRootName.value = ''
  const first = list.find(f => f.webkitRelativePath)
  if (first) projectRootName.value = first.webkitRelativePath.split('/')[0] || ''
  // 清空 input，保证下次选择同一目录也能触发 change
  event.target.value = ''
  // 全量上传模式：选完目录立即上传
  if (uploadMode.value === 'full') doUpload()
}

function resetPick() {
  // 切换上传方式时清空已选文件与勾选
  pickedFiles.value = []
  checkedPaths.value = []
  projectRootName.value = ''
}

async function doUpload() {
  if (!pickedFiles.value.length) return ElMessage.warning('请先选择项目文件夹')
  // 部分上传：只提交勾选的文件
  const checkedSet = new Set(checkedPaths.value)
  const targets = uploadMode.value === 'partial'
    ? pickedFiles.value.filter(x => checkedSet.has(x.path))
    : pickedFiles.value
  if (!targets.length) return ElMessage.warning('请勾选要上传的文件')
  const data = new FormData()
  targets.forEach(x => {
    data.append('relative_paths', x.path)
    data.append('files', x.file)
  })
  data.append('conflict_policy', 'replace')
  uploading.value = true
  try {
    const result = (await api.post(`/objects/projects/${id}/files/batch`, data)).data
    const failed = result.results.filter(x => !x.success)
    ElMessage[failed.length ? 'warning' : 'success'](failed.length ? `${failed.length} 个文件失败` : `已上传 ${result.results.length} 个文件`)
    if (!failed.length) {
      uploadDialog.value = false
      pickedFiles.value = []
      checkedPaths.value = []
      projectRootName.value = ''
      load()
    }
  } finally {
    uploading.value = false
  }
}

async function openEdit(row) {
  const response = await api.get(`/objects/projects/${id}/files/${row.id}/download`, { responseType: 'blob' })
  Object.assign(edit, { id: row.id, path: row.relative_path, content: await response.data.text() })
  editorDialog.value = true
}
async function saveEdit() {
  const data = new FormData()
  data.append('file', new Blob([edit.content], { type: 'text/plain;charset=utf-8' }), edit.path.split('/').pop())
  await api.put(`/objects/projects/${id}/files/${edit.id}`, data)
  ElMessage.success('文件已保存')
  editorDialog.value = false
  load()
}
async function remove(row) {
  await ElMessageBox.confirm(`确认删除 ${row.relative_path}？`)
  await api.delete(`/objects/projects/${id}/files/${row.id}`)
  load()
}
async function saveMembers() {
  await api.put(`/objects/projects/${id}/members`, members.value)
  memberDialog.value = false
  ElMessage.success('项目成员已保存')
}
function addMember() { members.value.push({ user_id: null, role: 'developer' }) }

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div><el-button link @click="router.push('/objects/projects')">← 返回测试项目</el-button><h2>{{ project.name }}</h2></div>
      <div class="toolbar">
        <el-button v-if="auth.user?.role === 'admin'" @click="memberDialog = true">项目成员</el-button>
        <el-button v-if="canWrite" type="primary" @click="router.push({ path: '/tasks/create', query: { project: id } })">发起测试</el-button>
        <el-button v-if="canWrite" type="primary" @click="uploadDialog = true">上传文件</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="project-tabs" @tab-change="onTabChange">
      <el-tab-pane label="文件目录" name="files">
    <div class="layout">
      <div class="card tree-card">
        <div class="tree-head">
          <b>文件目录</b>
          <el-button v-if="selectedDir" link type="primary" @click="selectedDir = ''">显示全部</el-button>
        </div>
        <PathTree :paths="allPaths" :selected="selectedDir" :height="560" empty-text="暂无文件，请先上传" @select="onTreeSelect"/>
      </div>

      <div class="card list-card">
        <div class="list-head">
          <span class="muted">{{ selectedDir || '全部文件' }} · {{ visibleFiles.length }} 个文件</span>
          <el-input v-model="search" placeholder="按路径搜索文件" clearable size="small" style="width:240px"/>
        </div>
        <el-table :data="visibleFiles" height="560">
          <el-table-column prop="relative_path" label="项目文件" min-width="380" show-overflow-tooltip>
            <template #default="{row}"><span class="path">{{ row.relative_path }}</span></template>
          </el-table-column>
          <el-table-column label="大小" width="100"><template #default="{row}">{{ (row.size / 1024).toFixed(1) }} KB</template></el-table-column>
          <el-table-column prop="updated_at" label="更新时间" width="180"><template #default="{row}">{{ new Date(row.updated_at).toLocaleString() }}</template></el-table-column>
          <el-table-column label="操作" width="180">
            <template #default="{row}">
              <el-button v-if="canWrite && EDITABLE.test(row.relative_path)" link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link @click="download(`/objects/projects/${id}/files/${row.id}/download`, row.relative_path.split('/').pop())">下载</el-button>
              <el-button v-if="canWrite" link type="danger" @click="remove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
      </el-tab-pane>

      <el-tab-pane name="tasks">
        <template #label>相关任务 <span v-if="tasks.length" class="tab-count">{{ tasks.length }}</span></template>
        <div class="card">
          <el-table :data="tasks" @row-click="row => router.push(`/tasks/${row.id}`)" style="cursor:pointer">
            <el-table-column prop="id" label="任务 ID" width="90" sortable/>
            <el-table-column label="执行器" min-width="150"><template #default="{row}"><span>{{ row.environment_name || row.environment_id }}</span></template></el-table-column>
            <el-table-column label="用例范围" min-width="200" show-overflow-tooltip><template #default="{row}"><span class="path">{{ row.testcase_scope?.path || '整个项目' }}</span></template></el-table-column>
            <el-table-column label="状态" width="110"><template #default="{row}"><StatusBadge :value="row.status"/></template></el-table-column>
            <el-table-column label="耗时" width="110"><template #default="{row}">{{ taskDuration(row) }}</template></el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180"><template #default="{row}">{{ new Date(row.created_at).toLocaleString() }}</template></el-table-column>
          </el-table>
          <el-empty v-if="!tasks.length" description="暂无相关任务"/>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="uploadDialog" title="上传项目文件" width="640" append-to-body>
      <p class="guide-tip">项目文件在平台中保持标准目录结构：<code>config</code> 运行配置、<code>testcase</code> 测试用例、<code>business</code> 业务封装、<code>testcase/casedata</code> 测试数据。</p>

      <el-tabs v-model="uploadMode" class="upload-tabs" @tab-change="resetPick">
        <el-tab-pane label="整个项目目录上传" name="full">
          <div class="mode-panel">
            <p class="mode-desc">选择本地项目根目录，读取整棵目录树后<b>自动上传全部文件</b>，无需逐个勾选。</p>
            <label class="dir-drop" :class="{ active: pickedFiles.length || uploading }">
              <input type="file" webkitdirectory hidden @change="choose">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
              <div class="dir-drop-text">
                <template v-if="uploading">
                  <b>正在上传 {{ pickedFiles.length }} 个文件…</b>
                  <span class="muted">请稍候，上传完成后自动刷新文件列表</span>
                </template>
                <template v-else-if="pickedFiles.length">
                  <b>已选择 {{ pickedFiles.length }} 个文件</b>
                  <span class="muted">根目录：{{ projectRootName }} · 点击可重新选择</span>
                </template>
                <template v-else>
                  <b>点击选择项目文件夹</b>
                  <span class="muted">选择后自动上传整个项目目录</span>
                </template>
              </div>
              <el-button size="small" type="primary" :loading="uploading" @click.stop>{{ uploading ? '上传中' : '选择文件夹' }}</el-button>
            </label>
            <el-alert type="info" :closable="false" show-icon class="mode-alert">
              顶层目录名会被自动剥离，最终保留 <code>config / testcase / business</code> 结构。
            </el-alert>
          </div>
        </el-tab-pane>

        <el-tab-pane label="勾选部分上传" name="partial">
          <div class="mode-panel">
            <p class="mode-desc">选择本地项目根目录，展示树形结构后<b>勾选需要上传的文件</b>，默认全选。</p>
            <label class="dir-drop" :class="{ active: pickedFiles.length }">
              <input type="file" webkitdirectory hidden @change="choose">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
              <div class="dir-drop-text">
                <template v-if="pickedFiles.length">
                  <b>已选择 {{ pickedFiles.length }} 个文件</b>
                  <span class="muted">根目录：{{ projectRootName }} · 点击可重新选择</span>
                </template>
                <template v-else>
                  <b>点击选择项目文件夹</b>
                  <span class="muted">展示目录树供勾选</span>
                </template>
              </div>
              <el-button size="small" type="primary" plain @click.stop>重新选择</el-button>
            </label>

            <div v-if="pickedFiles.length" class="tree-panel">
              <div class="tree-check-tip">
                已勾选 <b>{{ checkedPaths.length }}</b> / {{ pickedFiles.length }} 个文件
                <el-button link type="primary" size="small" @click="checkedPaths = pickedFiles.map(x => x.path)">全选</el-button>
                <el-button link size="small" @click="checkedPaths = []">清空</el-button>
              </div>
              <CaseCheckTree :paths="treeRelativePaths" v-model="checkedPaths" :show-hidden="true" :height="260"/>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>

      <template #footer>
        <el-button @click="uploadDialog = false">取消</el-button>
        <el-button v-if="uploadMode === 'partial'" type="primary" :disabled="!checkedPaths.length" :loading="uploading" @click="doUpload">
          上传 {{ checkedPaths.length }} 个文件
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editorDialog" :title="edit.path" width="880" append-to-body>
      <CodeEditor v-model="edit.content" :language="langOf(edit.path)" :height="480" :readonly="!canWrite"/>
      <template #footer>
        <el-button @click="editorDialog = false">取消</el-button>
        <el-button v-if="canWrite" type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="memberDialog" title="项目成员" width="580" append-to-body>
      <div v-for="(item, index) in members" :key="index" class="member">
        <el-select v-model="item.user_id" placeholder="选择用户">
          <el-option v-for="u in users.filter(x => x.role !== 'admin')" :key="u.id" :label="u.username" :value="u.id"/>
        </el-select>
        <el-select v-model="item.role"><el-option label="开发人员" value="developer"/><el-option label="查看人员" value="viewer"/></el-select>
        <el-button link type="danger" @click="members.splice(index, 1)">删除</el-button>
      </div>
      <el-button link type="primary" @click="addMember">+ 添加成员</el-button>
      <template #footer>
        <el-button @click="memberDialog = false">取消</el-button>
        <el-button type="primary" @click="saveMembers">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.layout { display: grid; grid-template-columns: 300px 1fr; gap: 16px; align-items: start; }
.tree-card { position: sticky; top: 20px; }
.tree-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.tree-head b { color: var(--text-primary); font-size: 14px; }
.list-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }
.path { font-family: Consolas, monospace; font-size: 12px; }
.project-tabs { margin-top: 4px; }
.tab-count { margin-left: 5px; padding: 1px 7px; border-radius: 10px; background: var(--primary-glow); color: var(--primary); font-size: 11px; font-weight: 700; }
.member { display: grid; grid-template-columns: 1fr 150px 60px; gap: 10px; margin-bottom: 10px; }
.page-head h2 { margin-top: 8px; }
.guide-tip { margin: 0 0 12px; font-size: 13px; color: var(--text-secondary); line-height: 1.6; }
.guide-tip code { font-family: Consolas, monospace; color: var(--accent); background: var(--accent-glow); padding: 1px 6px; border-radius: 5px; }
.upload-tabs { margin-top: 4px; }
.mode-panel { padding: 14px 2px 4px; }
.mode-desc { font-size: 13px; color: var(--text-secondary); line-height: 1.6; margin: 0 0 14px; }
.dir-drop { display: flex; align-items: center; gap: 14px; padding: 20px 18px; border: 1.5px dashed var(--border-strong); border-radius: 12px; background: var(--surface-soft); cursor: pointer; transition: border-color .2s, background .2s; }
.dir-drop:hover { border-color: var(--primary); }
.dir-drop.active { border-color: var(--primary); border-style: solid; background: var(--primary-glow); }
.dir-drop > svg { width: 32px; height: 32px; flex: 0 0 auto; color: var(--text-muted); }
.dir-drop.active > svg { color: var(--primary); }
.dir-drop-text { flex: 1; display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.dir-drop-text b { font-size: 14px; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dir-drop-text .muted { font-size: 12.5px; color: var(--text-muted); }
.mode-alert { margin-top: 14px; }
.mode-alert code { font-family: Consolas, monospace; color: var(--accent); }
.tree-panel { margin-top: 14px; }
.tree-check-tip { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--text-secondary); margin-bottom: 8px; }
.tree-check-tip b { color: var(--primary); }
@media (max-width: 1300px) { .layout { grid-template-columns: 1fr; } .tree-card { position: static; } }
</style>
