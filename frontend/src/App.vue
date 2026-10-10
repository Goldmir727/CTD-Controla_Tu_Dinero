<template>
  <div>
    <header class="topbar">
      <Logo :width="44" />
      <strong>CTD</strong>
      <span style="flex: 1"></span>
      <button v-if="showHeaderCta" class="btn-new desktop-only" @click="$router.push('/movimientos/nuevo')">+ Nuevo movimiento</button>
      <button v-if="isLanding && !authed" class="btn-ghost" @click="$router.push('/login')">Entrar</button>
      <button v-if="authed" class="gear" @click="$router.push('/config')" aria-label="Ajustes"><i class="bi bi-gear"></i></button>
    </header>
    <router-view :key="tick" />
    <CapturaRapida @guardado="refrescarTrasCaptura" />
    <InstallPrompt />
    <UpdateBanner />
    <CookieBanner />
    <ConsentBanner />
    <div v-if="fan" class="fan-backdrop" @click="fan = false">
      <div class="fan" @click.stop>
        <button @click="go('ingreso')">+ Ingreso</button>
        <button @click="go('gasto')">− Gasto</button>
      </div>
    </div>
    <button v-if="showFab" class="fab" @click="fan = true">+</button>
    <nav v-if="authed" class="bottom-nav">
      <div class="nav-side">
        <router-link to="/inicio">Inicio</router-link>
        <router-link to="/movimientos">Movs</router-link>
      </div>
      <span class="fab-gap"></span>
      <div class="nav-side">
        <router-link to="/plan">Plan</router-link>
        <router-link to="/analisis">Datos</router-link>
        <router-link to="/asesor">Asesor</router-link>
      </div>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import InstallPrompt from './components/InstallPrompt.vue'
import UpdateBanner from './components/UpdateBanner.vue'
import CookieBanner from './components/CookieBanner.vue'
import ConsentBanner from './components/ConsentBanner.vue'
import CapturaRapida from './components/CapturaRapida.vue'
import Logo from './components/Logo.vue'
import api from './services/api'
import { useAuth } from './stores/auth'
import { useTema } from './composables/useTema'
const route = useRoute()

// Tras una captura hay que recargar la vista actual. Cambiar la key del router-view
// remonta el componente y sus onMounted vuelven a pedir datos: es mas fiable que
// un evento global al que cada vista tenga que suscribirse.
const tick = ref(0)
function refrescarTrasCaptura(n: number) {
  if (n > 0) tick.value += 1
}
const router = useRouter()
const auth = useAuth()
const fan = ref(false)
const authed = computed(() => auth.isAuthed)
const isLanding = computed(() => route.path === '/')
let ultimaCheck = 0

function aLanding() {
  router.push('/').catch(() => {})
}

/** Si no hay sesión válida, el store se limpia y la UI deja de fingir cuenta. */
async function validarSesion(forzar = false) {
  if (!auth.isAuthed) return
  const ahora = Date.now()
  if (!forzar && ahora - ultimaCheck < 5 * 60 * 1000) return
  ultimaCheck = ahora
  try {
    await api.get('/auth/me')
  } catch {
    auth.clear()
    aLanding()
  }
}

function onSesionCerrada() {
  auth.clear()
  aLanding()
}

function onVisible() {
  if (!document.hidden) void validarSesion()
}

onMounted(() => {
  useTema().init()
  window.addEventListener('ctd:sesion-cerrada', onSesionCerrada)
  document.addEventListener('visibilitychange', onVisible)
  void validarSesion(true)
})
onUnmounted(() => {
  window.removeEventListener('ctd:sesion-cerrada', onSesionCerrada)
  document.removeEventListener('visibilitychange', onVisible)
})
// Acción global solo donde tiene sentido: Plan tiene sus propios CTA (presupuesto/meta).
const showHeaderCta = computed(() => authed.value && ['/inicio', '/movimientos'].includes(route.path))
const showFab = computed(() => authed.value && !['/', '/login', '/registro', '/onboarding', '/2fa', '/movimientos/nuevo'].includes(route.path))
function go(tipo: string) { fan.value = false; router.push({ path: '/movimientos/nuevo', query: { tipo } }) }
</script>

<style>
.topbar { display: flex; align-items: center; gap: 8px; max-width: 720px; margin: 0 auto; padding: 12px 16px; }
.btn-new { background: var(--mint); color: var(--navy); border: 0; border-radius: 12px; padding: 10px 14px; font-weight: 800; }
.gear { background: none; border: 1px solid var(--line); border-radius: 12px; padding: 8px 12px; font-size: 18px; cursor: pointer; }
/* Única acción primaria por contexto: FAB solo móvil, botón header solo escritorio */
@media (max-width: 899px) { .desktop-only { display: none; } }
@media (min-width: 900px) { .fab { display: none; } }
.fan-backdrop { position: fixed; inset: 0; background: rgba(5,11,59,.45); z-index: 30; display: flex; align-items: flex-end; justify-content: center; padding-bottom: 170px; }
.fan { display: grid; gap: 8px; }
.fan button { background: var(--navy); color: #fff; border: 1px solid var(--mint); border-radius: 14px; padding: 12px 22px; font-weight: 700; }
</style>
