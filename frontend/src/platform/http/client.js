import axios from 'axios'
import { ElMessage } from 'element-plus'
import { auth } from '../auth/session'

export const api = axios.create({ baseURL: '/api/v1', timeout: 120000 })
api.interceptors.request.use(config => { if (auth.token) config.headers.Authorization = `Bearer ${auth.token}`; return config })
function errorMessage(detail) {
  if (Array.isArray(detail)) return detail.map(item => item?.msg || String(item)).join('；')
  if (detail && typeof detail === 'object') return detail.message || JSON.stringify(detail)
  return detail
}
api.interceptors.response.use(r => r, error => {
  if (error.response?.status === 401) { auth.clear(); if (location.pathname !== '/login') location.href = '/login' }
  ElMessage.error(errorMessage(error.response?.data?.detail) || error.message || '请求失败')
  return Promise.reject(error)
})

export async function download(url, filename) {
  const { data } = await api.get(url, { responseType: 'blob' })
  const link = document.createElement('a'); link.href = URL.createObjectURL(data); link.download = filename; link.click(); URL.revokeObjectURL(link.href)
}
