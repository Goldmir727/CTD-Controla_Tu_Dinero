<template>
  <div v-if="visible && slotVisible" class="cookie-bar floating-banner" role="region" aria-label="Aviso de cookies">
    <p><strong>Cookies necesarias.</strong> <span class="sub">Guardamos tu sesión y preferencias en este dispositivo. Sin rastreadores.</span>
      <a href="#" @click.prevent="$router.push('/cookies')">Ver política</a></p>
    <div class="row2">
      <button class="btn-mint" @click="elegir('all')">Aceptar</button>
      <button class="btn-ghost" @click="elegir('min')">Solo necesarias</button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref, watchEffect } from 'vue'
import { useBannerSlot } from '../composables/useBannerSlot'

const { visible: slotVisible, pedir } = useBannerSlot('cookies')
const visible = ref(!localStorage.getItem('ctd-cookies'))

// Solo se muestra si además le toca el hueco: así no se apila con el aviso de
// actualización ni tapa la barra de navegación.
watchEffect(() => pedir(visible.value))
onBeforeUnmount(() => pedir(false))

function elegir(v: string) {
  localStorage.setItem('ctd-cookies', v)
  visible.value = false
}
</script>
<style>
.cookie-bar {
  background: var(--surface); color: var(--ink);
  border: 1px solid var(--line); border-radius: 16px;
  padding: 14px; box-shadow: var(--shadow);
  display: grid; gap: 10px;
  animation: rise 240ms ease-out;
}
.cookie-bar p { margin: 0; font-size: 14px; }
.cookie-bar .row2 { display: flex; gap: 8px; }
.cookie-bar .row2 > * { flex: 1; }
</style>
