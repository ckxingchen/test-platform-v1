import { auth } from '@/platform/auth/session'

// 面向用户界面的术语统一映射（后端表名/字段名保持 environment/resource 不变）。
// 禁止在界面文案中散落「环境 / 运行器 / Mission」等旧词。
//
// 说明：groupObjects / groupResources / groupTasks / groupUsers 仅作为
// 侧边栏菜单与面包屑的「分组容器词」，不进入任何页面级实体文案；
// 页面内实体词统一为「测试项目 / 测试框架 / 执行器 / 任务 / Agent」。
// 「资源管理」一级菜单直达执行器列表（实体词仍为「执行器」）。
export const TERM = {
  project: '测试项目',
  framework: '测试框架',
  executor: '执行器',
  agent: 'Agent',
  task: '任务',
  // 菜单 / 面包屑分组词（仅容器用途）
  groupObjects: '对象管理',
  groupResources: '资源管理',
  groupTasks: '任务管理',
  groupUsers: '用户管理'
}

// 权限 helper：系统角色为 admin 时返回 true。
export const isAdmin = () => auth.user?.role === 'admin'
