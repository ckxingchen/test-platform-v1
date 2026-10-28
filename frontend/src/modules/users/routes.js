const UserListPage = () => import('./pages/UserListPage.vue')

export const userRoutes = [
  { path: 'users', component: UserListPage, meta: { title: '用户管理', group: '用户管理', admin: true } }
]
