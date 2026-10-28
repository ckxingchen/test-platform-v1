export const legacyRoutes = [
  { path: 'objects', redirect: '/objects/agents' },
  { path: 'resources', redirect: '/executors' },
  { path: 'resources/agents', redirect: '/objects/agents' },
  { path: 'resources/frameworks', redirect: '/objects/frameworks' },
  { path: 'resources/projects', redirect: '/objects/projects' },
  { path: 'resources/projects/:id', redirect: to => `/objects/projects/${to.params.id}` },
  { path: 'environments', redirect: '/executors' },
  { path: 'environments/executors', redirect: '/executors' },
  { path: 'environments/executors/:id', redirect: to => `/executors/${to.params.id}` },
  { path: 'execution', redirect: '/executors' },
  { path: 'execution/executors', redirect: '/executors' },
  { path: 'execution/executors/:id', redirect: to => `/executors/${to.params.id}` },
  { path: 'execution/tasks', redirect: '/tasks' },
  { path: 'execution/tasks/create', redirect: '/tasks/create' },
  { path: 'execution/tasks/:id', redirect: to => `/tasks/${to.params.id}` }
]
