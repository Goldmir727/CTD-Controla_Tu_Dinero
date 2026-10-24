<template>
  <Teleport to="body">
    <div v-if="estado.abierto" class="confirm-backdrop" @click.self="responderConfirm(false)">
      <div
        ref="card"
        class="confirm-card"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-titulo"
        :aria-describedby="estado.mensaje ? 'confirm-mensaje' : undefined"
      >
        <h2 id="confirm-titulo" class="confirm-titulo">{{ estado.titulo }}</h2>
        <p v-if="estado.mensaje" id="confirm-mensaje" class="sub confirm-mensaje">{{ estado.mensaje }}</p>
        <div class="confirm-acciones">
          <!-- El foco arranca en Cancelar: en una acción destructiva el pulgar
               no debe poder confirmar sin querer con un doble toque. -->
          <button class="confirm-cancelar" data-autofocus @click="responderConfirm(false)">
            {{ estado.cancelar }}
          </button>
          <button :class="['confirm-ok', { 'is-danger': estado.peligro }]" @click="responderConfirm(true)">
            {{ estado.ok }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDialog } from '../composables/useDialog'
import { estadoConfirm, responderConfirm } from '../composables/useConfirm'

const estado = estadoConfirm
const abierto = computed(() => estado.abierto)
const card = ref<HTMLElement | null>(null)

// Escape y clic fuera = cancelar, que es la salida segura en un borrado.
useDialog(abierto, card, () => responderConfirm(false))
</script>
<style>
.confirm-backdrop {
  position: fixed; inset: 0; z-index: var(--z-modal);
  background: rgba(5, 11, 59, .55);
  display: grid; place-items: center;
  padding: 16px calc(16px + env(safe-area-inset-left)) calc(16px + env(safe-area-inset-bottom));
}
.confirm-card {
  width: 100%; max-width: 380px;
  background: var(--surface); color: var(--ink);
  border: 1px solid var(--line); border-radius: 20px;
  padding: 20px; box-shadow: var(--shadow);
  display: grid; gap: 10px;
  animation: rise 180ms ease-out;
}
.confirm-titulo { margin: 0; font-size: 17px; line-height: 1.3; }
.confirm-mensaje { margin: 0; }
.confirm-acciones { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 6px; }
.confirm-acciones button {
  min-height: 48px; border-radius: 12px; font-weight: 800; font-size: 15px;
  cursor: pointer; border: 1px solid transparent;
  display: inline-flex; align-items: center; justify-content: center;
}
.confirm-cancelar { background: none; border-color: var(--line); color: var(--ink); }
.confirm-ok { background: var(--navy); color: #FFFFFF; }
.confirm-ok.is-danger { background: var(--danger-text); color: #FFFFFF; }
/* En oscuro --danger-text es un rojo claro: con texto blanco no llega a AA. */
[data-theme='dark'] .confirm-ok.is-danger { background: #FF8A8A; color: var(--navy); }
.confirm-acciones button:focus-visible {
  outline: none; box-shadow: 0 0 0 3px rgba(0, 255, 171, .35);
}
@media (prefers-reduced-motion: reduce) { .confirm-card { animation: none; } }
</style>
