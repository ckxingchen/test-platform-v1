<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { TERM } from '@/shared/constants/terminology'
import StatusBadge from '@/shared/components/StatusBadge.vue'

const route = useRoute(), router = useRouter(), id = route.params.id
const data = ref(null)
const loading = ref(false)

const environment = computed(() => data.value?.environment || {})
const framework = computed(() => data.value?.framework || null)
const deployHistory = computed(() => data.value?.deploy_history || [])
const taskHistory = computed(() => data.value?.task_history || [])
const concurrency = computed(() => data.value?.concurrency || { max: 0, active: 0 })

function shortSha(sha) { return sha ? sha.slice(0, 8) : '-' }
function duration(row) {
  if (!row.started_at) return '-'
  const end = row.finished_at ? new Date(row.finished_at) : new Date()
  const sec = Math.max(0, Math.round((end - new Date(row.started_at)) / 1000))
  if (sec < 60) return `${sec} 秒`
  if (sec < 3600) return `${Math.floor(sec / 60)} 分 ${sec % 60} 秒`
  return `${Math.floor(sec / 3600)} 时 ${Math.floor((sec % 3600) / 60)} 分`
}

async function load() {
  loading.value = true
  try { data.value = (await api.get(`/environments/${id}/overview`)).data }
  finally { loading.value = false }
}

onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-head">
      <div>
        <el-button link @click="router.push('/executors')">← 返回执行器</el-button>
        <h2>{{ environment.name || '执行器详情' }}
          <StatusBadge :value="environment.agent_status"/>
          <StatusBadge :value="environment.framework_status"/>
        </h2>
        <div class="muted">{{ environment.host }}:{{ environment.ssh_port }} · Agent 目录 {{ environment.agent_home }}</div>
      </div>
    </div>

    <div class="overview">
      <div class="ov-card"><span>测试框架</span><b>{{ environment.framework_name || '-' }}</b><small>{{ framework ? `${framework.os || '-'} / ${framework.arch || '-'}` : '' }}</small></div>
      <div class="ov-card"><span>已部署框架版本</span><b>{{ shortSha(environment.framework_sha256) }}</b><small>最新：{{ shortSha(framework?.latest_sha256) }}</small></div>
      <div class="ov-card"><span>并发占用</span><b>{{ concurrency.active }} / {{ concurrency.max }}</b><small>ACTIVE / MAX</small></div>
      <div class="ov-card"><span>归属人</span><b>{{ environment.owner_name || '-' }}</b><small>创建人</small></div>
    </div>

    <el-alert v-if="environment.framework_status === 'failed'" title="框架部署失败，请重新部署" type="error" show-icon :closable="false" style="margin-bottom:16px"/>

    <el-tabs>
      <el-tab-pane name="deployments">
        <template #label>部署历史 <span class="tab-count">{{ deployHistory.length }}</span></template>
        <div class="card">
          <el-timeline v-if="deployHistory.length">
            <el-timeline-item v-for="d in deployHistory" :key="d.id" :timestamp="new Date(d.created_at).toLocaleString()" placement="top">
              <div class="deploy-item">
                <b>#{{ d.id }} · <StatusBadge :value="d.status"/></b>
                <span class="path">框架版本 {{ shortSha(d.framework_sha256) }}</span>
                <span v-if="d.error_message" class="err-text">{{ d.error_message }}</span>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无部署记录"/>
        </div>
      </el-tab-pane>

      <el-tab-pane name="tasks">
        <template #label>任务历史 <span class="tab-count">{{ taskHistory.length }}</span></template>
        <div class="card">
          <el-table :data="taskHistory" @row-click="row => router.push(`/tasks/${row.id}`)" style="cursor:pointer">
            <el-table-column prop="id" label="任务 ID" width="90" sortable/>
            <el-table-column label="测试项目" min-width="150"><template #default="{row}">{{ row.project_name || row.project_id }}</template></el-table-column>
            <el-table-column label="用例范围" min-width="180" show-overflow-tooltip><template #default="{row}"><span class="path">{{ row.testcase_scope?.path || '整个项目' }}</span></template></el-table-column>
            <el-table-column label="状态" width="110"><template #default="{row}"><StatusBadge :value="row.status"/></template></el-table-column>
            <el-table-column label="耗时" width="110"><template #default="{row}">{{ duration(row) }}</template></el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180"><template #default="{row}">{{ new Date(row.created_at).toLocaleString() }}</template></el-table-column>
          </el-table>
          <el-empty v-if="!taskHistory.length" description="暂无任务历史"/>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.page-head h2 { margin: 8px 0 4px; display: flex; gap: 12px; align-items: center; }
.overview { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 16px; }
.ov-card { padding: 17px 18px; border: 1px solid var(--border-color); border-radius: 12px; background: var(--surface); box-shadow: var(--shadow-soft); }
.ov-card span { color: var(--text-muted); font-size: 12px; }
.ov-card b { display: block; margin-top: 8px; color: var(--text-primary); font-size: 18px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ov-card small { display: block; margin-top: 6px; color: var(--text-muted); font-size: 11px; }
.tags-card { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; padding: 14px 18px; }
.tags-card .label { color: var(--text-muted); font-size: 12px; }
.tag { margin-right: 2px; }
.tab-count { margin-left: 5px; padding: 1px 7px; border-radius: 10px; background: var(--primary-glow); color: var(--primary); font-size: 11px; font-weight: 700; }
.deploy-item { display: flex; flex-direction: column; gap: 6px; }
.path { font-family: Consolas, monospace; font-size: 12px; color: var(--text-secondary); }
.err-text { color: var(--danger); font-size: 12px; }
@media (max-width: 1100px) { .overview { grid-template-columns: repeat(2, 1fr); } }
</style>
