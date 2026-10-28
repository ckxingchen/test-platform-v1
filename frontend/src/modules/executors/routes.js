const ExecutorListPage = () => import('./pages/ExecutorListPage.vue')
const ExecutorDetailPage = () => import('./pages/ExecutorDetailPage.vue')

export const executorRoutes = [
  { path: 'executors', component: ExecutorListPage, meta: { title: '执行器', group: '资源管理' } },
  { path: 'executors/:id', component: ExecutorDetailPage, meta: { title: '执行器详情', group: '资源管理' } }
]
