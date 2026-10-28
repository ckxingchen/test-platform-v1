import { TERM } from '@/shared/constants/terminology'

export const navigation = [
  { path: '/', label: '仪表盘', icon: 'dashboard' },
  { path: '/objects', label: TERM.groupObjects, icon: 'folder', children: [
    { path: '/objects/agents', label: 'AGENT 管理', icon: 'robot' },
    { path: '/objects/frameworks', label: '框架管理', icon: 'cube' },
    { path: '/objects/projects', label: '项目管理', icon: 'briefcase' }
  ]},
  { path: '/executors', label: TERM.groupResources, icon: 'server' },
  { path: '/tasks', label: TERM.groupTasks, icon: 'tasks' },
  { path: '/users', label: TERM.groupUsers, icon: 'user', admin: true }
]
