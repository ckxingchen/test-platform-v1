import { reactive } from 'vue'

export const auth = reactive({
  token: localStorage.getItem('token') || '',
  user: JSON.parse(localStorage.getItem('user') || 'null'),
  set(token, user) { this.token = token; this.user = user; localStorage.setItem('token', token); localStorage.setItem('user', JSON.stringify(user)) },
  clear() { this.token = ''; this.user = null; localStorage.removeItem('token'); localStorage.removeItem('user') }
})

