<template>
  <div v-if="mostrarBanner" class="install-bar">
    <Logo :width="36" />
    <div style="flex: 1"><strong>Instala CTD</strong><small>Acceso rápido, abre al instante y con los datos ya guardados.</small></div>
    <button class="btn-mint" @click="instalar">Instalar</button>
    <button class="btn-ghost" style="color: #fff; border-color: rgba(255,255,255,.3)" @click="descartar">No</button>
  </div>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import Logo from './Logo.vue'
import { usePwaInstall } from '../composables/usePwaInstall'
const { mostrarBanner, instalar, descartar, capturar, rescatar } = usePwaInstall()
function alInstalar() {
  rescatar()
}
onMounted(() => {
  rescatar()
  window.addEventListener('beforeinstallprompt', capturar)
  window.addEventListener('ctd:instalable', alInstalar)
})
onUnmounted(() => {
  window.removeEventListener('beforeinstallprompt', capturar)
  window.removeEventListener('ctd:instalable', alInstalar)
})
</script>
