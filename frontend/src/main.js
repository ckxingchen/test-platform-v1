import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './shared/theme/theme.css'
import './styles.css'
import App from './app/App.vue'
import router from './app/router'
import { initTheme } from './shared/theme'

initTheme()
createApp(App).use(ElementPlus).use(router).mount('#app')
