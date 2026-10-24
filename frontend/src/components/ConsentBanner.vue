<template>
  <div v-if="visible" class="consent-backdrop">
    <div
      ref="card"
      class="consent-card"
      role="dialog"
      aria-modal="true"
      aria-labelledby="consent-titulo"
    >
      <p id="consent-titulo" class="consent-titulo">
        <strong>Actualizamos nuestros documentos.</strong>
      </p>
      <p class="sub">
        Para seguir usando CTD acepta los
        <a href="#" @click.prevent="$router.push('/terminos')">Términos</a> y la
        <a href="#" @click.prevent="$router.push('/datos')">Política de Datos</a>.
      </p>
      <label class="check">
        <input v-model="t" type="checkbox" data-autofocus />
        Acepto los Términos y Condiciones
      </label>
      <label class="check">
        <input v-model="d" type="checkbox" />
        Acepto la Política de Tratamiento de Datos
      </label>
      <button class="btn-mint" :disabled="!t || !d || busy" @click="aceptar">
        <span v-if="busy" class="spinner"></span>Aceptar y continuar
      </button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import api from '../services/api'
import { useAuth } from '../stores/auth'
import { useDialog } from '../composables/useDialog'

const auth = useAuth()
const visible = ref(false)
const card = ref<HTMLElement | null>(null)
const t = ref(false)
const d = ref(false)
const busy = ref(false)

// Es un consentimiento legal: no se puede cerrar con Escape ni clic fuera.
useDialog(visible, card, () => {}, { esc: false })

onMounted(async () => {
  if (!auth.isAuthed) return
  try {
    const { data } = await api.get('/auth/me')
    visible.value = !data.acepta_datos
  } catch { /* sin sesión válida: nada que pedir */ }
})
async function aceptar() {
  busy.value = true
  try {
    await api.post('/auth/consentimiento', { acepta_terminos: true, acepta_datos: true })
    visible.value = false
  } finally { busy.value = false }
}
</script>
<style>
.check{display:flex;gap:8px;align-items:flex-start;font-size:13px;color:var(--ink-soft)}
.check input{margin-top:3px;accent-color:var(--mint-dark)}
.consent-backdrop {
  position: fixed; inset: 0; z-index: 95;
  background: rgba(5, 11, 59, .72);
  display: grid; place-items: center;
  padding: 16px calc(16px + env(safe-area-inset-left)) calc(16px + env(safe-area-inset-bottom));
  overflow-y: auto;
}
.consent-card {
  width: 100%; max-width: 420px;
  background: var(--surface); color: var(--ink);
  border: 1px solid var(--line); border-radius: 20px;
  padding: 20px; box-shadow: var(--shadow);
  display: grid; gap: 12px;
}
.consent-titulo { margin: 0; font-size: 16px; }
.consent-card .sub { margin: 0; }
.consent-card a { color: var(--mint-text); font-weight: 700; }
</style>
