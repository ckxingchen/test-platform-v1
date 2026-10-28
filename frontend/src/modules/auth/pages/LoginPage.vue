<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { auth } from '@/platform/auth/session'
import ThemeToggle from '@/shared/theme/ThemeToggle.vue'

const form = reactive({ username: 'admin', password: 'admin123' }), loading = ref(false), router = useRouter()
async function submit() {
  loading.value = true
  try {
    const token = (await api.post('/auth/login', form)).data.access_token
    auth.token = token
    localStorage.setItem('token', token)
    const user = (await api.get('/auth/me')).data
    auth.set(token, user)
    router.push('/')
  } finally { loading.value = false }
}
</script>

<template>
  <main class="login">
    <div class="login-grid"/><div class="scan-line"/><div class="orb orb-one"/><div class="orb orb-two"/><div class="orb orb-three"/>
    <div class="theme-position"><ThemeToggle/></div>
    <section class="intro">
      <div class="intro-mark"><span>KW</span><i/><b/></div>
      <div class="overline"><span/>AUTOMATION COMMAND CENTER</div>
      <h1>让每一次测试<br><em>可见、可控、可信</em></h1>
      <p>统一连接测试框架、执行器与项目任务。<br>从配置到报告，全流程实时掌控。</p>
      <div class="features"><div><b>01</b><span>分布式执行器</span><small>DISTRIBUTED</small></div><div><b>02</b><span>实时任务日志</span><small>REAL-TIME</small></div><div><b>03</b><span>文件版本冻结</span><small>VERSIONED</small></div></div>
    </section>
    <section class="login-panel">
      <div class="panel-edge top"/><div class="panel-edge bottom"/>
      <header><div><small>SECURE ACCESS / 安全访问</small><h2>登录控制台</h2></div><span class="secure-dot"/></header>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名 / USER ID"><el-input v-model="form.username" size="large" autocomplete="username" placeholder="请输入用户名"/></el-form-item>
        <el-form-item label="密码 / PASSWORD"><el-input v-model="form.password" type="password" show-password size="large" autocomplete="current-password" placeholder="请输入密码" @keyup.enter="submit"/></el-form-item>
        <el-button class="login-button" type="primary" size="large" :loading="loading" @click="submit"><span>进入系统</span><b>→</b></el-button>
      </el-form>
      <footer><span><i/> ENCRYPTED CONNECTION</span><span>KW PLATFORM · V1.0</span></footer>
    </section>
  </main>
</template>

<style scoped>
.login{position:relative;min-height:100vh;overflow:hidden;display:grid;grid-template-columns:minmax(480px,1fr) 430px;align-items:center;gap:8vw;padding:7vh 10vw;color:var(--text-primary);background:radial-gradient(circle at 18% 24%,var(--primary-glow),transparent 28%),radial-gradient(circle at 86% 82%,var(--accent-glow),transparent 30%),var(--bg-base)}.login-grid{position:absolute;inset:-30%;opacity:.72;transform:perspective(700px) rotateX(62deg) translateY(20%);transform-origin:center bottom;background-image:linear-gradient(var(--bg-grid) 1px,transparent 1px),linear-gradient(90deg,var(--bg-grid) 1px,transparent 1px);background-size:45px 45px;mask-image:radial-gradient(ellipse at center,black,transparent 67%)}.scan-line{position:absolute;z-index:1;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--primary),transparent);box-shadow:0 0 18px var(--primary);opacity:.23;animation:scan 7s linear infinite}.orb{position:absolute;border:1px solid var(--border-strong);border-radius:50%;opacity:.45;animation:float 9s ease-in-out infinite}.orb::after{content:"";position:absolute;left:50%;top:-3px;width:5px;height:5px;border-radius:50%;background:var(--primary);box-shadow:0 0 9px var(--primary)}.orb-one{width:260px;height:260px;left:-110px;top:-90px}.orb-two{width:110px;height:110px;right:8%;bottom:-38px;animation-delay:-3s}.orb-three{width:48px;height:48px;left:48%;top:11%;animation-delay:-6s}.theme-position{position:absolute;z-index:4;right:32px;top:28px}.intro,.login-panel{position:relative;z-index:2}.intro{max-width:650px}.intro-mark{position:relative;width:64px;height:64px;display:grid;place-items:center;margin-bottom:38px;border:1px solid var(--border-strong);border-radius:17px;color:var(--primary-bright);background:var(--primary-glow);font:900 18px/1 Inter,sans-serif;letter-spacing:.08em;box-shadow:inset 0 0 25px var(--primary-glow),0 0 34px var(--primary-glow)}.intro-mark::before,.intro-mark::after{content:"";position:absolute;width:11px;height:11px;border-color:var(--primary);border-style:solid}.intro-mark::before{left:6px;top:6px;border-width:1px 0 0 1px}.intro-mark::after{right:6px;bottom:6px;border-width:0 1px 1px 0}.intro-mark i{position:absolute;inset:-10px;border:1px dashed var(--border-color);border-radius:22px;animation:rotate 18s linear infinite}.intro-mark b{position:absolute;right:-13px;top:13px;width:4px;height:4px;border-radius:50%;background:var(--primary);box-shadow:0 0 11px var(--primary)}.overline{display:flex;align-items:center;gap:10px;color:var(--primary);font:700 10px/1 Inter,sans-serif;letter-spacing:.22em}.overline span{width:34px;height:1px;background:linear-gradient(90deg,var(--primary),transparent)}.intro h1{margin:20px 0 22px;font-size:clamp(38px,4.2vw,62px);line-height:1.15;letter-spacing:-.045em}.intro h1 em{color:transparent;background:linear-gradient(100deg,var(--primary-bright),var(--accent));background-clip:text;font-style:normal;text-shadow:0 0 35px var(--primary-glow)}.intro>p{color:var(--text-secondary);font-size:15px;line-height:1.9;letter-spacing:.025em}.features{display:flex;gap:13px;margin-top:42px}.features>div{min-width:132px;padding:13px 15px;border:1px solid var(--border-color);border-radius:11px;background:var(--surface-soft);backdrop-filter:blur(12px)}.features b,.features span,.features small{display:block}.features b{color:var(--primary);font:700 9px/1 Inter,sans-serif}.features span{margin-top:9px;font-size:12px;font-weight:700}.features small{margin-top:5px;color:var(--text-muted);font:600 8px/1 Inter,sans-serif;letter-spacing:.13em}.login-panel{width:430px;padding:34px 34px 25px;border:1px solid var(--border-color);border-radius:18px;background:var(--surface);box-shadow:var(--shadow-card);backdrop-filter:blur(22px)}.login-panel::before{content:"";position:absolute;inset:8px;pointer-events:none;border:1px solid color-mix(in srgb,var(--border-color) 42%,transparent);border-radius:12px}.panel-edge{position:absolute;width:45px;height:13px;border-color:var(--primary);border-style:solid}.panel-edge.top{top:-1px;left:26px;border-width:1px 0 0 1px}.panel-edge.bottom{right:26px;bottom:-1px;border-width:0 1px 1px 0}.login-panel header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:30px}.login-panel header small{color:var(--primary);font:700 9px/1 Inter,sans-serif;letter-spacing:.16em}.login-panel h2{margin:10px 0 0;font-size:25px;letter-spacing:-.02em}.secure-dot{width:8px;height:8px;margin-top:4px;border-radius:50%;background:var(--success);box-shadow:0 0 11px var(--success);animation:secure 1.8s ease infinite}.login-panel :deep(.el-form-item__label){color:var(--text-muted);font-size:10px;font-weight:700;letter-spacing:.08em}.login-panel :deep(.el-input__wrapper){min-height:47px}.login-button{width:100%;height:49px;margin-top:8px;display:flex;justify-content:center}.login-button :deep(span){width:100%;display:flex;justify-content:space-between;align-items:center;padding:0 5px}.login-button b{font-size:18px}.login-panel footer{position:relative;display:flex;justify-content:space-between;margin-top:28px;padding-top:18px;border-top:1px solid var(--border-color);color:var(--text-muted);font:600 8px/1 Inter,sans-serif;letter-spacing:.08em}.login-panel footer i{display:inline-block;width:4px;height:4px;margin-right:4px;border-radius:50%;background:var(--success)}@keyframes scan{from{top:-2%}to{top:102%}}@keyframes float{50%{transform:translateY(-14px) rotate(8deg)}}@keyframes rotate{to{transform:rotate(360deg)}}@keyframes secure{50%{opacity:.35}}@media(max-width:1180px){.login{grid-template-columns:1fr 410px;padding:7vh 5vw;gap:5vw}.features>div{min-width:112px}}@media(prefers-reduced-motion:reduce){.scan-line,.orb,.intro-mark i,.secure-dot{animation:none}}
</style>
