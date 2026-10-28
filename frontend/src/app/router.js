import { createRouter, createWebHistory } from 'vue-router'
import { auth } from '@/platform/auth/session'
import MainLayout from '@/app/layout/MainLayout.vue'
import { authRoutes } from '@/modules/auth/routes'
import { dashboardRoutes } from '@/modules/dashboard/routes'
import { userRoutes } from '@/modules/users/routes'
import { agentPackageRoutes } from '@/modules/objects/agent_packages/routes'
import { frameworkRoutes } from '@/modules/objects/frameworks/routes'
import { projectRoutes } from '@/modules/objects/projects/routes'
import { executorRoutes } from '@/modules/executors/routes'
import { taskRoutes } from '@/modules/tasks/routes'
import { legacyRoutes } from '@/app/routes_legacy'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    ...authRoutes,
    {
      path: '/',
      component: MainLayout,
      children: [
        ...dashboardRoutes,
        ...userRoutes,
        ...agentPackageRoutes,
        ...frameworkRoutes,
        ...projectRoutes,
        ...executorRoutes,
        ...taskRoutes,
        ...legacyRoutes
      ]
    }
  ]
})

router.beforeEach(to => {
  if (to.path !== '/login' && !auth.token) return '/login'
  if (to.meta.admin && auth.user?.role !== 'admin') return '/'
  if (to.path === '/login' && auth.token) return '/'
})

export default router
