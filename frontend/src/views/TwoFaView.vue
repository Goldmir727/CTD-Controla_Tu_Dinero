<template>
  <main class="page">
    <h2>Verificación en 2 pasos</h2>
    <p class="sub">Enviamos un código de 6 dígitos a tu Gmail. Puedes copiarlo y pegarlo aquí.</p>
    <input v-model="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="000000"
      aria-label="Código de 6 dígitos" class="input" style="font-size: 28px; letter-spacing: 0.4em; text-align: center" />
    <button class="btn-primary" style="margin-top: 12px" @click="verificar">Entrar</button>
    <button class="link" @click="reenviar">Reenviar código</button>
    <p v-if="e" class="alert" role="alert" aria-live="assertive">{{ e }}</p>
    <p class="sub">Próximamente: Google Authenticator y Entrar con Google.</p>
  </main>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'
import { useAuth } from '../stores/auth'
const route = useRoute(); const router = useRouter()
const auth = useAuth()
const code = ref(''); const e = ref('')
const correo = ((route.query.correo as string) || localStorage.getItem('pending_2fa_email') || '').trim().toLowerCase()
async function verificar() {
  e.value = ''
  try {
    if (route.query.modo === 'activar') {
      await api.post('/auth/2fa/activar', { code: code.value })
      router.push('/config')
    } else {
      const { data } = await api.post('/auth/2fa/verificar', { correo, code: code.value })
      auth.setTokens(data.access_token, data.refresh_token)
      localStorage.removeItem('pending_2fa_email')
      await auth.entrar(router)
    }
  } catch { e.value = 'Código inválido o vencido (10 min, 5 intentos).' }
}
async function reenviar() {
  e.value = ''
  try { await api.post('/auth/2fa/solicitar', { correo }); e.value = 'Código reenviado. Revisa tu correo.' }
  catch (err: unknown) {
    const d = (err as { response?: { status?: number; data?: { detail?: string } } }).response
    e.value = d?.status === 429 ? (d?.data?.detail ?? 'Espera antes de pedir otro código.') : 'No se pudo reenviar. Intenta más tarde.'
  }
}
</script>
<style>.sub{font-size:13px;color:var(--ink-soft)}</style>
