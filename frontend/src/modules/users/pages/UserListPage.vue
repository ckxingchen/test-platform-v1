<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'
const rows=ref([]),dialog=ref(false),formRef=ref(),submitting=ref(false)
const form=reactive({username:'',password:'',role:'developer'})
function validateUsername(_,value,callback){const username=value?.trim()||'';if(!username)callback(new Error('请输入用户名'));else if(username.length<2||username.length>64)callback(new Error('用户名长度为 2～64 个字符'));else callback()}
function validatePassword(_,value,callback){if(!value)callback(new Error('请输入初始密码'));else if(value.length<6)callback(new Error('密码至少 6 个字符'));else callback()}
const rules={username:[{validator:validateUsername,trigger:'blur'}],password:[{validator:validatePassword,trigger:'blur'}],role:[{required:true,message:'请选择角色',trigger:'change'}]}
async function load(){rows.value=(await api.get('/users')).data}
async function create(){if(!(await formRef.value.validate().catch(()=>false)))return;submitting.value=true;try{await api.post('/users',{...form,username:form.username.trim()});ElMessage.success('用户已创建');dialog.value=false;Object.assign(form,{username:'',password:'',role:'developer'});await load()}finally{submitting.value=false}}
async function save(row){await api.put(`/users/${row.id}`,{role:row.role,enabled:row.enabled});ElMessage.success('已保存')}
onMounted(load)
</script>
<template><div class="page"><div class="page-head"><h2>用户管理</h2><el-button type="primary" @click="dialog=true">新建用户</el-button></div><div class="card"><el-table :data="rows"><el-table-column prop="username" label="用户名"/><el-table-column label="角色" width="180"><template #default="{row}"><el-select v-model="row.role"><el-option label="管理员" value="admin"/><el-option label="开发人员" value="developer"/><el-option label="查看人员" value="viewer"/></el-select></template></el-table-column><el-table-column label="启用" width="100"><template #default="{row}"><el-switch v-model="row.enabled"/></template></el-table-column><el-table-column label="操作" width="100"><template #default="{row}"><el-button link type="primary" @click="save(row)">保存</el-button></template></el-table-column></el-table></div><el-dialog v-model="dialog" title="新建用户" width="440" append-to-body><el-form ref="formRef" :model="form" :rules="rules" label-position="top"><el-form-item label="用户名" prop="username"><el-input v-model="form.username" maxlength="64"/></el-form-item><el-form-item label="初始密码" prop="password"><el-input v-model="form.password" type="password" show-password/></el-form-item><el-form-item label="角色" prop="role"><el-select v-model="form.role" style="width:100%"><el-option label="开发人员" value="developer"/><el-option label="查看人员" value="viewer"/><el-option label="管理员" value="admin"/></el-select></el-form-item></el-form><template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" :loading="submitting" @click="create">确定</el-button></template></el-dialog></div></template>
