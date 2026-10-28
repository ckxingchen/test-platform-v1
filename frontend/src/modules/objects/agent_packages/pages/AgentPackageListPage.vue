<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, download } from '../api'
import { isAdmin, TERM } from '@/shared/constants/terminology'

const rows = ref([])
const dialog = ref(false)
const uploading = ref(false)
const fileInput = ref(null)
const form = reactive({ file: null, name: 'kw-agent', os: 'linux', arch: 'x86_64' })

async function load() {
  rows.value = (await api.get('/objects/agents')).data
}

function pickFile() { fileInput.value?.click() }
function onFileChange(event) {
  const file = event.target.files?.[0]
  if (!file) return
  form.file = file
  // 文件名带 os 线索时自动切换
  const lower = file.name.toLowerCase()
  if (lower.includes('win')) form.os = 'windows'
  else if (lower.includes('linux')) form.os = 'linux'
  if (lower.includes('arm64') || lower.includes('aarch64')) form.arch = 'arm64'
  else if (lower.includes('x64') || lower.includes('amd64')) form.arch = 'x86_64'
  event.target.value = ''
}

const saveDisabledReason = computed(() => {
  if (!form.name?.trim()) return '请填写 Agent 名称'
  if (!form.file) return '请选择 Agent 发布包（zip / tar.gz）'
  return ''
})

async function upload() {
  const reason = saveDisabledReason.value
  if (reason) { ElMessage.warning(reason); return }
  uploading.value = true
  try {
    const data = new FormData()
    data.append('file', form.file)
    data.append('name', form.name.trim())
    data.append('os', form.os)
    data.append('arch', form.arch)
    // 不手动设置 Content-Type：浏览器会自动为 FormData 追加 boundary，前端其他上传点（Frameworks/ProjectDetail）均如此。
    await api.post('/objects/agents', data)
    ElMessage.success('Agent 包已上传')
    dialog.value = false
    form.file = null
    load()
  } finally { uploading.value = false }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除 Agent 包 ${row.name}（${row.os}/${row.arch}）？重新上传相同平台将无法回退。`)
  await api.delete(`/objects/agents/${row.id}`)
  ElMessage.success('已删除')
  load()
}

function timeText(value) { return value ? new Date(value).toLocaleString() : '-' }

function sizeText(size) {
  if (!size) return '-'
  if (size > 1024 * 1024) return (size / 1024 / 1024).toFixed(1) + ' MB'
  if (size > 1024) return (size / 1024).toFixed(1) + ' KB'
  return size + ' B'
}

async function downloadPackage(row) {
  await download(`/objects/agents/${row.id}/download`, row.file_name)
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>AGENT</h2>
        <div class="muted">按（名称 / OS / 架构）维护当前最新 Agent 包；重新上传覆盖旧包后，执行器页将提示「待重新部署」</div>
      </div>
      <el-button v-if="isAdmin()" type="primary" @click="dialog = true">上传 Agent 包</el-button>
    </div>

    <div class="card">
      <el-table :data="rows">
        <el-table-column prop="name" label="Agent 名称" min-width="130"/>
        <el-table-column label="平台" min-width="120">
          <template #default="{row}">
            <el-tag size="small" :type="row.os === 'windows' ? 'primary' : 'success'">{{ row.os }}</el-tag>
            <span style="margin-left:6px">{{ row.arch }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="file_name" label="文件" min-width="180" show-overflow-tooltip/>
        <el-table-column label="大小" width="90">
          <template #default="{row}">{{ sizeText(row.size) }}</template>
        </el-table-column>
        <el-table-column label="SHA256" width="150">
          <template #default="{row}"><code class="sha">{{ row.sha256?.slice(0, 12) || '-' }}…</code></template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="150">
          <template #default="{row}">{{ timeText(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column v-if="isAdmin()" label="操作" width="150" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" @click="downloadPackage(row)">下载</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无 Agent 包，请先上传 Windows / Linux 发布包"/>
        </template>
      </el-table>
    </div>

    <el-dialog v-model="dialog" title="上传 Agent 包" width="560" append-to-body>
      <el-alert type="info" :closable="false" class="guide-alert"
        title="发布包要求：压缩包顶层必须包含 bin/ 目录（bin/kw-agent.exe 或 bin/kw-agent）；重新上传相同 (名称+OS+架构) 会覆盖当前最新包"/>
      <el-form label-position="top">
        <el-form-item label="Agent 名称" required>
          <el-input v-model="form.name" placeholder="kw-agent"/>
        </el-form-item>
        <el-form-item label="操作系统 / 架构" required>
          <el-row :gutter="14" style="width:100%">
            <el-col :span="12">
              <el-select v-model="form.os" style="width:100%">
                <el-option label="Linux" value="linux"/>
                <el-option label="Windows" value="windows"/>
              </el-select>
            </el-col>
            <el-col :span="12">
              <el-select v-model="form.arch" style="width:100%">
                <el-option label="x86_64" value="x86_64"/>
                <el-option label="arm64" value="arm64"/>
              </el-select>
            </el-col>
          </el-row>
        </el-form-item>
        <el-form-item label="发布包文件" required>
          <div class="file-picker" @click="pickFile">
            <template v-if="form.file">
              <b>{{ form.file.name }}</b>
              <span class="muted">（{{ sizeText(form.file.size) }}）点击重新选择</span>
            </template>
            <template v-else><span class="muted">点击选择 .zip（Windows）或 .tar.gz（Linux）</span></template>
          </div>
          <input ref="fileInput" type="file" accept=".zip,.tar.gz,.tgz" style="display:none" @change="onFileChange"/>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="upload">上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.sha { font-family: Consolas, monospace; font-size: 12px; }
.file-picker { width: 100%; padding: 14px; border: 1px dashed var(--border-strong); border-radius: 8px; cursor: pointer; text-align: center; transition: border-color .2s; }
.file-picker:hover { border-color: var(--primary); }
.guide-alert { margin-bottom: 16px; }
</style>
