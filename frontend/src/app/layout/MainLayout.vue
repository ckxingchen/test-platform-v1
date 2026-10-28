<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { auth } from '@/platform/auth/session'
import ThemeToggle from '@/shared/theme/ThemeToggle.vue'
import MenuIcon from '@/shared/components/MenuIcon.vue'
import { navigation } from '@/app/navigation'

const route = useRoute(), router = useRouter()
// 菜单结构：仪表盘 / 对象管理{AGENT管理,框架管理,项目管理} / 资源管理(执行器) / 任务管理 / 用户管理。
// 分组词仅作为侧边栏容器名，不进入页面文案；「资源管理」「任务管理」为一级直达菜单。
const navs = navigation
const activeNav = computed(() => {
  if (route.path.startsWith('/objects/projects/')) return '/objects/projects'
  if (route.path.startsWith('/executors/')) return '/executors'
  if (route.path.startsWith('/tasks/')) return '/tasks'
  return route.path
})
// 面包屑：由 meta.group（分组）+ meta.title（页面）组成；无分组（如仪表盘）或分组与标题相同（如用户管理）时仅展示单层。
const breadcrumb = computed(() => {
  const group = route.meta.group
  const title = route.meta.title || '控制台'
  return group && group !== title ? [group, title] : [title]
})
const roleName = computed(() => ({ admin: '管理员', developer: '开发人员', viewer: '查看人员' }[auth.user?.role] || auth.user?.role))
const initials = computed(() => (auth.user?.username || 'U').slice(0, 2).toUpperCase())
function logout() { auth.clear(); router.push('/login') }
</script>

<template>
  <el-container class="shell">
    <el-aside width="244px" class="aside">
      <div class="brand"><div class="logo"><span>KW</span><i/></div><div class="brand-copy"><b>自动化测试平台</b><small>TEST OPERATIONS</small></div></div>
      <div class="system-state"><span class="pulse"/><div><small>SYSTEM STATUS</small><b>ALL SYSTEMS ONLINE</b></div></div>
      <div class="nav-caption">NAVIGATION / 导航</div>
      <el-menu :default-active="activeNav" router class="menu">
        <template v-for="item in navs.filter(x=>!x.admin||auth.user?.role==='admin')" :key="item.path">
          <el-sub-menu v-if="item.children" :index="item.path">
            <template #title>
              <span class="nav-item"><MenuIcon :name="item.icon"/><span class="nav-label">{{item.label}}</span></span>
            </template>
            <el-menu-item v-for="child in item.children" :key="child.path" :index="child.path">
              <span class="nav-item sub"><MenuIcon :name="child.icon" :size="16"/><span class="nav-label">{{child.label}}</span></span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="item.path">
            <span class="nav-item"><MenuIcon :name="item.icon"/><span class="nav-label">{{item.label}}</span><i class="nav-dot"/></span>
          </el-menu-item>
        </template>
      </el-menu>
      <div class="aside-foot"><span>CORE</span><b>V1.0</b><i/></div>
    </el-aside>
    <el-container class="workspace">
      <el-header class="header">
        <div class="location"><small>KW CONSOLE</small><template v-for="(seg, i) in breadcrumb" :key="seg"><span>/</span><b :class="{ dim: i < breadcrumb.length - 1 }">{{ seg }}</b></template></div>
        <div class="header-tools"><ThemeToggle/><div class="user-chip"><span class="avatar">{{initials}}</span><div><b>{{auth.user?.username}}</b><small>{{roleName}}</small></div></div><el-button class="logout" link @click="logout">退出系统</el-button></div>
      </el-header>
      <el-main class="main"><div class="grid-layer"/><router-view v-slot="{ Component }"><transition name="route-fade" mode="out-in"><component :is="Component" :key="route.path"/></transition></router-view></el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.shell{min-height:100vh;background:var(--bg-base)}.aside{position:relative;z-index:3;display:flex;flex-direction:column;color:var(--text-primary);background:var(--sidebar-bg);border-right:1px solid var(--border-color);box-shadow:8px 0 36px rgba(0,0,0,.08);backdrop-filter:blur(20px)}.aside::after{content:"";position:absolute;top:0;right:-1px;width:1px;height:140px;background:linear-gradient(transparent,var(--primary),transparent);box-shadow:0 0 12px var(--primary)}.brand{height:76px;display:flex;align-items:center;gap:13px;padding:0 19px;border-bottom:1px solid var(--border-color)}.logo{position:relative;width:42px;height:42px;display:grid;place-items:center;border:1px solid var(--border-strong);border-radius:12px;color:var(--primary-bright);background:var(--primary-glow);font:800 13px/1 Inter,sans-serif;letter-spacing:.07em;box-shadow:inset 0 0 14px var(--primary-glow),0 0 18px var(--primary-glow)}.logo::before,.logo::after{content:"";position:absolute;width:5px;height:5px;border-color:var(--primary);border-style:solid}.logo::before{top:4px;left:4px;border-width:1px 0 0 1px}.logo::after{right:4px;bottom:4px;border-width:0 1px 1px 0}.logo i{position:absolute;width:3px;height:3px;right:-2px;top:8px;border-radius:50%;background:var(--primary);box-shadow:0 0 7px var(--primary)}.brand-copy b{display:block;font-size:14px}.brand-copy small{display:block;margin-top:4px;color:var(--text-muted);font:600 9px/1 Inter,sans-serif;letter-spacing:.19em}.system-state{margin:17px 15px 10px;padding:11px 12px;display:flex;align-items:center;gap:10px;border:1px solid color-mix(in srgb,var(--success) 20%,transparent);border-radius:10px;background:color-mix(in srgb,var(--success) 6%,transparent)}.system-state .pulse{width:7px;height:7px;border-radius:50%;background:var(--success);box-shadow:0 0 10px var(--success);animation:system-pulse 1.8s ease infinite}.system-state small,.system-state b{display:block}.system-state small{color:var(--text-muted);font-size:8px;letter-spacing:.13em}.system-state b{margin-top:3px;color:var(--success);font-size:9px;letter-spacing:.08em}.nav-caption{padding:15px 20px 7px;color:var(--text-muted);font:600 9px/1 Inter,sans-serif;letter-spacing:.16em}.menu{border:0;padding:0 10px}.menu :deep(.el-menu-item){position:relative;height:50px;margin:4px 0;padding:0 14px!important;border:1px solid transparent;border-radius:10px;color:var(--text-secondary);font-size:16px;font-weight:500;letter-spacing:.01em}.menu :deep(.el-menu-item .nav-item){display:flex;align-items:center;gap:11px;width:100%}.menu :deep(.el-menu-item .nav-item .nav-label){font-size:16px;font-weight:500;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.menu :deep(.el-menu-item:hover){color:var(--text-primary);background:var(--surface-hover)}.menu :deep(.el-menu-item.is-active){color:var(--primary-bright);border-color:var(--border-strong);background:linear-gradient(90deg,var(--primary-glow),transparent);box-shadow:inset 3px 0 0 var(--primary)}.nav-dot{position:absolute;right:13px;width:4px;height:4px;border-radius:50%;background:currentColor;opacity:.35}.is-active .nav-dot{opacity:1;box-shadow:0 0 8px var(--primary)}.aside-foot{margin:auto 16px 17px;height:34px;display:flex;align-items:center;gap:7px;padding:0 10px;color:var(--text-muted);border-top:1px solid var(--border-color);font:600 9px/1 Inter,sans-serif;letter-spacing:.12em}.aside-foot b{color:var(--text-secondary)}.aside-foot i{margin-left:auto;width:24px;height:1px;background:linear-gradient(90deg,var(--primary),transparent)}.workspace{min-width:0}.header{position:relative;z-index:2;height:76px;display:flex;align-items:center;justify-content:space-between;padding:0 28px;border-bottom:1px solid var(--border-color);background:var(--header-bg);backdrop-filter:blur(18px)}.location{display:flex;align-items:center;gap:10px}.location small{color:var(--primary);font:700 10px/1 Inter,sans-serif;letter-spacing:.16em}.location span{color:var(--text-muted)}.location b{font-size:14px}.location b.dim{color:var(--text-muted);font-weight:600}.header-tools{display:flex;align-items:center;gap:12px}.user-chip{height:42px;display:flex;align-items:center;gap:10px;padding:0 12px 0 5px;border-left:1px solid var(--border-color)}.avatar{width:33px;height:33px;display:grid;place-items:center;border:1px solid var(--border-strong);border-radius:10px;color:var(--primary-bright);background:var(--primary-glow);font-size:11px;font-weight:800}.user-chip b,.user-chip small{display:block}.user-chip b{font-size:12px}.user-chip small{margin-top:3px;color:var(--text-muted);font-size:10px}.logout{color:var(--text-muted)}.main{position:relative;padding:0;overflow:auto;background:radial-gradient(circle at 90% -10%,var(--accent-glow),transparent 34%),var(--bg-base)}.grid-layer{position:absolute;inset:0;pointer-events:none;opacity:.75;background-image:linear-gradient(var(--bg-grid) 1px,transparent 1px),linear-gradient(90deg,var(--bg-grid) 1px,transparent 1px);background-size:34px 34px;mask-image:linear-gradient(to bottom,black,transparent 75%)}.route-fade-enter-active,.route-fade-leave-active{transition:.18s ease}.route-fade-enter-from,.route-fade-leave-to{opacity:0}@keyframes system-pulse{50%{opacity:.35;transform:scale(.75)}}
.menu :deep(.el-sub-menu__title){height:50px;margin:4px 0;padding:0 14px!important;border-radius:10px;color:var(--text-secondary);font-size:16px;font-weight:600;letter-spacing:.01em}.menu :deep(.el-sub-menu__title:hover){color:var(--text-primary);background:var(--surface-hover)}.menu :deep(.el-sub-menu__title .nav-item){display:flex;align-items:center;gap:11px;width:100%}.menu :deep(.el-sub-menu__title .nav-label){font-size:16px;font-weight:600;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.menu :deep(.el-sub-menu .el-menu){background:transparent}.menu :deep(.el-sub-menu .el-menu-item){height:42px;padding-left:0!important}.menu :deep(.el-sub-menu .el-menu-item .nav-item){font-size:14.5px;font-weight:500;padding-left:30px}.menu :deep(.el-sub-menu .el-menu-item .nav-item .nav-label){font-size:14.5px;font-weight:500}
</style>
