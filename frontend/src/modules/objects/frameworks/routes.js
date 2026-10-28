const FrameworkListPage = () => import('./pages/FrameworkListPage.vue')

export const frameworkRoutes = [
  { path: 'objects/frameworks', component: FrameworkListPage, meta: { title: '框架管理', group: '对象管理' } }
]
