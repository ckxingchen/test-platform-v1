const TaskListPage = () => import('./pages/TaskListPage.vue')
const TaskCreatePage = () => import('./pages/TaskCreatePage.vue')
const TaskDetailPage = () => import('./pages/TaskDetailPage.vue')

export const taskRoutes = [
  { path: 'tasks', component: TaskListPage, meta: { title: '任务', group: '任务管理' } },
  { path: 'tasks/create', component: TaskCreatePage, meta: { title: '新建任务', group: '任务管理' } },
  { path: 'tasks/:id', component: TaskDetailPage, meta: { title: '任务详情', group: '任务管理' } }
]
