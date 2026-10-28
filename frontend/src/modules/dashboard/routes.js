const DashboardPage = () => import('./pages/DashboardPage.vue')

export const dashboardRoutes = [
  { path: '', component: DashboardPage, meta: { title: '仪表盘' } }
]
