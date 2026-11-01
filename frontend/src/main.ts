import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'
import { initPerf } from './composables/usePerf'
import router from './router'
import { useOffline } from './stores/offline'
import 'bootstrap-icons/font/bootstrap-icons.css'
import './styles/tokens.css'

initPerf()
createApp(App).use(createPinia()).use(router).mount('#app')

// Escucha online/offline y sincroniza la cola al recuperar la red. Antes solo se
// sincronizaba si `pendientes` ya era mayor que cero, pero ese contador arranca
// en cero y nadie lo refrescaba: los cambios guardados sin red no se enviaban
// nunca hasta abrir una vista que los volviera a pedir.
useOffline().iniciar()
