<script setup>
import { reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, download } from '../api'
import { isAdmin, TERM } from '@/shared/constants/terminology'
import StatusBadge from '@/shared/components/StatusBadge.vue'

const rows = ref([]), dialog = ref(false), file = ref(null), loading = ref(false)
const expanded = reactive({}), envs = reactive({})

// —— 上传前填写的框架元信息（OS / 架构 / 名称 / 入口均在界面输入）——
const target = reactive({ name: 'test-framework', os: 'linux', arch: 'x86_64', runner_path: 'driver/自动化测试框架' })

// —— 各操作系统的默认执行器入口（Windows 为 .exe）——
const runnerPathByOs = { linux: 'driver/自动化测试框架', windows: 'driver/自动化测试框架.exe' }
watch(() => target.os, (os) => { target.runner_path = runnerPathByOs[os] ?? '' })

async function load() { rows.value = (await api.get('/objects/frameworks')).data }
function choose(event) { file.value = event.target.files[0] || null }
async function upload() {
  if (!file.value) { ElMessage.warning('请先选择压缩包文件'); return }
  if (!target.name.trim()) { ElMessage.warning('请填写框架名称'); return }
  if (!target.runner_path.trim()) { ElMessage.warning('请填写执行器入口路径'); return }
  loading.value = true
  try {
    const data = new FormData()
    data.append('artifact', file.value)
    data.append('name', target.name.trim())
    data.append('os', target.os)
    data.append('arch', target.arch)
    data.append('runner_path', target.runner_path.trim())
    await api.post('/objects/frameworks', data)
    ElMessage.success('测试框架已上传并通过校验')
    dialog.value = false
    file.value = null
    load()
  } finally { loading.value = false }
}
async function remove(row) {
  const message = row.used_by_count > 0
    ? `该框架正被 ${row.used_by_count} 个执行器使用，删除后这些执行器将无法正常部署。确认删除 ${row.name}？`
    : `确认删除 ${row.name}？`
  await ElMessageBox.confirm(message, '删除测试框架', { type: 'warning', confirmButtonText: '确认删除' })
  await api.delete(`/objects/frameworks/${row.id}`)
  load()
}
async function toggleExecutors(row) {
  if (expanded[row.id]) { expanded[row.id] = false; return }
  if (!envs[row.id]) envs[row.id] = (await api.get(`/objects/frameworks/${row.id}/environments`)).data
  expanded[row.id] = true
}
function meta(row, key, fallback = '-') { return row.metadata_json?.[key] ?? fallback }
load()
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>{{ TERM.framework }}</h2>
        <div class="muted">同一框架名可按「操作系统 + CPU 架构」保存多个版本；同名同架构上传后替换为最新版本</div>
      </div>
      <el-button v-if="isAdmin()" type="primary" @click="dialog=true">上传测试框架</el-button>
    </div>

    <div class="object-grid">
      <div v-for="row in rows" :key="row.id" class="card object-card">
        <div class="object-head">
          <div class="object-icon">FW</div>
          <div><h3>{{ row.name }}</h3><span>{{ row.os ?? meta(row,'os') }} / {{ row.arch ?? meta(row,'arch') }}</span></div>
          <span class="status status-success">LATEST</span>
        </div>
        <div class="meta">
          <div><span>运行入口</span><b>{{ meta(row,'runner_path') }}</b></div>
          <div><span>文件数量</span><b>{{ meta(row,'file_count') }}</b></div>
          <div><span>被使用</span><b>{{ row.used_by_count }} 个执行器</b></div>
          <div><span>更新时间</span><b>{{ new Date(row.updated_at).toLocaleString() }}</b></div>
        </div>
        <div class="object-actions">
          <el-button link @click="toggleExecutors(row)">{{ expanded[row.id] ? '收起执行器' : `查看执行器 (${row.used_by_count})` }}</el-button>
          <el-button v-if="isAdmin()" link @click="download(`/objects/frameworks/${row.id}/download`, row.name+'-framework.tar.gz')">下载</el-button>
          <el-button v-if="isAdmin()" link type="danger" @click="remove(row)">删除</el-button>
        </div>

        <div v-if="expanded[row.id]" class="used-by">
          <div v-for="e in (envs[row.id] || [])" :key="e.id" class="used-by-item">
            <span class="env-name">{{ e.name }}</span>
            <span class="muted">{{ e.host }}</span>
            <StatusBadge :value="e.framework_status"/>
          </div>
          <el-empty v-if="!((envs[row.id] || []).length)" description="暂无执行器使用该框架" :image-size="60"/>
        </div>
      </div>
      <el-empty v-if="!rows.length" description="暂无测试框架">
        <el-button v-if="isAdmin()" type="primary" @click="dialog=true">上传测试框架</el-button>
      </el-empty>
    </div>

    <el-dialog v-model="dialog" title="上传测试框架" width="560" append-to-body>
      <el-form label-position="top" class="gen-form">
        <el-form-item label="框架名称（字母 / 数字 / 点 / 横线 / 下划线）">
          <el-input v-model="target.name" placeholder="kw-framework" maxlength="64"/>
        </el-form-item>
        <div class="gen-grid">
          <el-form-item label="操作系统">
            <el-select v-model="target.os" style="width:100%">
              <el-option label="Linux" value="linux"/>
              <el-option label="Windows" value="windows"/>
            </el-select>
          </el-form-item>
          <el-form-item label="CPU 架构">
            <el-select v-model="target.arch" style="width:100%">
              <el-option label="x86_64" value="x86_64"/>
              <el-option label="arm64" value="arm64"/>
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="执行器入口（相对压缩包根目录，可含子目录与后缀）">
          <el-input v-model="target.runner_path" placeholder="driver/自动化测试框架"/>
        </el-form-item>
        <el-form-item label="压缩包">
          <input type="file" accept=".zip,.gz,.tgz" @change="choose" class="file-input">
        </el-form-item>
        <el-alert type="info" :closable="false" title="上传提示" class="guide-alert">
          <template #default>
            <div class="guide-text">压缩包内应包含以下目录结构：</div>
            <pre class="guide-tree">├── driver/      执行器入口所在目录
├── plugins/     插件目录
├── testsuits/   测试项目目录（空目录）
├── pytest.ini   测试配置文件
└── README.md    说明文档</pre>
          </template>
        </el-alert>
      </el-form>

      <template #footer>
        <el-button @click="dialog=false">取消</el-button>
        <el-button type="primary" :loading="loading" :disabled="loading" @click="upload">校验并上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.object-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(390px,1fr));gap:16px}
.object-card{padding:20px}
.object-head{display:flex;align-items:center;gap:13px}
.object-head h3{margin:0 0 6px}
.object-head span:not(.status){color:var(--text-muted);font-size:12px}
.object-head .status{margin-left:auto}
.object-icon{width:48px;height:48px;display:grid;place-items:center;border:1px solid var(--border-strong);border-radius:12px;color:var(--primary);background:var(--primary-glow);font:800 10px/1 Inter,sans-serif;letter-spacing:.08em}
.meta{display:grid;grid-template-columns:1fr 1fr;gap:13px;margin-top:20px;padding:15px;border-radius:10px;background:var(--surface-soft)}
.meta span,.meta b{display:block}
.meta span{color:var(--text-muted);font-size:10px}
.meta b{margin-top:5px;color:var(--text-secondary);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.object-actions{display:flex;justify-content:flex-end;margin-top:12px}
.used-by{margin-top:14px;padding:10px 14px;border:1px solid var(--border-color);border-radius:10px;background:var(--surface-soft)}
.used-by-item{display:flex;align-items:center;gap:12px;padding:7px 0;border-bottom:1px dashed var(--border-color)}
.used-by-item:last-child{border-bottom:none}
.used-by-item .env-name{color:var(--text-primary);font-size:13px;font-weight:600}
.used-by-item .muted{margin-left:auto;font-size:12px}
.gen-form{margin-top:6px}
.gen-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.file-input{display:block;width:100%;box-sizing:border-box;padding:8px;border:1px dashed var(--border-strong);border-radius:8px}
.guide-alert{--el-alert-bg-color:var(--surface-soft);margin-top:4px;background-color:var(--surface-soft);border:1px solid var(--border-color)}
.guide-alert :deep(.el-alert__title){color:var(--text-secondary)}
.guide-alert :deep(.el-alert__content){color:var(--text-secondary)}
.guide-text{margin-bottom:6px;color:var(--text-secondary)}
.guide-tree{margin:0;color:var(--text-secondary);font:12px/1.8 Consolas,Menlo,Monaco,monospace;white-space:pre}
</style>
