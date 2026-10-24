<template>
  <Teleport to="body">
    <!-- La región existe siempre (aunque esté vacía): si se creara junto al
         texto, los lectores de pantalla no anunciarían el primer aviso. -->
    <div class="toast-stack" role="status" aria-live="polite">
      <div v-for="t in lista" :key="t.id" :class="['toast', `toast--${t.tipo}`]">
        <i :class="['bi', icono(t.tipo)]" aria-hidden="true"></i>
        <span class="toast-texto">{{ t.texto }}</span>
        <button class="toast-x" aria-label="Ocultar aviso" @click="quitar(t.id)">
          <i class="bi bi-x-lg" aria-hidden="true"></i>
        </button>
      </div>
    </div>
  </Teleport>
</template>
<script setup lang="ts">
import { useToast, type TipoToast } from '../composables/useToast'

const { lista, quitar } = useToast()
const icono = (t: TipoToast) =>
  t === 'error' ? 'bi-exclamation-triangle' : t === 'info' ? 'bi-info-circle' : 'bi-check-circle'
</script>
<style>
.toast-stack {
  position: fixed; left: 50%; transform: translateX(-50%);
  top: calc(var(--safe-top) + 10px);
  z-index: var(--z-toast);
  width: min(92vw, 420px);
  display: grid; gap: 8px;
  /* El hueco no debe bloquear toques en la cabecera; cada aviso sí. */
  pointer-events: none;
}
.toast {
  pointer-events: auto;
  display: flex; align-items: center; gap: 10px;
  background: var(--navy); color: #FFFFFF;
  border: 1px solid rgba(255, 255, 255, .16);
  border-left: 4px solid var(--mint);
  border-radius: 14px;
  padding: 8px 8px 8px 12px;
  box-shadow: var(--shadow);
  font-size: 13.5px; font-weight: 600; line-height: 1.3;
  animation: toast-in 200ms ease-out;
}
.toast--error { border-left-color: #FF8A8A; }
.toast--info { border-left-color: var(--mint-dim); }
.toast > i { font-size: 16px; flex: none; color: var(--mint); }
.toast--error > i { color: #FF8A8A; }
.toast--info > i { color: var(--mint-dim); }
.toast-texto { flex: 1; min-width: 0; }
.toast-x {
  background: none; border: 0; color: #FFFFFF; opacity: .7; cursor: pointer;
  width: 36px; height: 36px; border-radius: 10px; flex: none;
  display: inline-flex; align-items: center; justify-content: center;
}
.toast-x:hover { opacity: 1; }
.toast-x:focus-visible { outline: none; box-shadow: 0 0 0 2px var(--mint); }
@keyframes toast-in { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) { .toast { animation: none; } }
</style>
