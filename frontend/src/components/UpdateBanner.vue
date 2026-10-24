<template>
  <div v-if="hayUpdate && slotVisible" class="update-bar floating-banner" role="status" aria-live="polite">
    <div style="flex: 1"><strong>Nueva versión disponible</strong><small>Mejoras y arreglos listos para ti.</small></div>
    <button class="btn-mint" :disabled="cargando" @click="ir">
      <span v-if="cargando" class="spinner"></span>Actualizar
    </button>
  </div>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref, watchEffect } from 'vue'
import { usePwaUpdate } from '../composables/usePwaUpdate'
import { useBannerSlot } from '../composables/useBannerSlot'
const { hayUpdate, aplicar } = usePwaUpdate()
const { visible: slotVisible, pedir } = useBannerSlot('update')
watchEffect(() => pedir(hayUpdate.value))
onBeforeUnmount(() => pedir(false))
const cargando = ref(false)
async function ir() {
  cargando.value = true
  await aplicar()
}
</script>
<style>
.update-bar {
  background: var(--navy); color: #fff; border-radius: 16px;
  padding: 12px 14px; display: flex; gap: 10px; align-items: center;
  box-shadow: var(--shadow); border: 1px solid var(--mint);
  animation: rise 240ms ease-out;
}
.update-bar small { opacity: 0.75; display: block; }
</style>
