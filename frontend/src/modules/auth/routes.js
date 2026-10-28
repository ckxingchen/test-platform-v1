const LoginPage = () => import('./pages/LoginPage.vue')

export const authRoutes = [
  { path: '/login', component: LoginPage, meta: { title: '登录' } }
]
