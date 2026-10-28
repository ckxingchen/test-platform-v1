const ProjectListPage = () => import('./pages/ProjectListPage.vue')
const ProjectDetailPage = () => import('./pages/ProjectDetailPage.vue')

export const projectRoutes = [
  { path: 'objects/projects', component: ProjectListPage, meta: { title: '项目管理', group: '对象管理' } },
  { path: 'objects/projects/:id', component: ProjectDetailPage, meta: { title: '项目管理', group: '对象管理' } }
]
