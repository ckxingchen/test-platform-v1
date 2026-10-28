const AgentPackageListPage = () => import('./pages/AgentPackageListPage.vue')

export const agentPackageRoutes = [
  { path: 'objects/agents', component: AgentPackageListPage, meta: { title: 'AGENT 管理', group: '对象管理' } }
]
