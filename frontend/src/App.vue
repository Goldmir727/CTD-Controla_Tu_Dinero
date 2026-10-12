<template>
<div :class="{ 'app-public': !authed }">
    <header class="topbar" :class="{ 'topbar--public': !authed }">
      <Logo :width="44" />
      <strong>CTD</strong>
      <span style="flex: 1"></span>
      <span data-tour="perfil" style="display:flex"><SelectorPerfil v-if="authed" @cambio="tick++" /></span>
      <button v-if="showHeaderCta" class="btn-new desktop-only" data-tour="nuevo-movimiento" @click="$router.push('/movimientos/nuevo')">+ Nuevo movimiento</button>
      <button v-if="isLanding && !authed" class="btn-ghost" @click="$router.push('/login')">Entrar</button>
      <button v-if="authed" class="gear" @click="abrirAyuda" aria-label="Ayuda" title="Ayuda"><i class="bi bi-question-lg"></i></button>
      <button v-if="authed" class="gear" data-tour="ajustes" @click="$router.push('/config')" aria-label="Ajustes"><i class="bi bi-gear"></i></button>
    </header>
    <router-view :key="tick" />
    <CapturaRapida @guardado="refrescarTrasCaptura" />
    <TourGuias ref="tour" :pais="ctxPais" />
    <InstallPrompt v-if="authed" />
    <UpdateBanner />
    <CookieBanner />
    <ConsentBanner />
    <div v-if="fan" class="fan-backdrop" @click="fan = false">
      <div class="fan" @click.stop>
        <button @click="go('ingreso')">+ Ingreso</button>
        <button @click="go('gasto')">− Gasto</button>
      </div>
    </div>
    <button v-if="showFab" class="fab" data-tour="nuevo-movimiento" @click="fan = true">+</button>
    <nav v-if="authed" class="bottom-nav" data-tour="nav">
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
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import InstallPrompt from './components/InstallPrompt.vue'
import UpdateBanner from './components/UpdateBanner.vue'
import CookieBanner from './components/CookieBanner.vue'
import ConsentBanner from './components/ConsentBanner.vue'
import CapturaRapida from './components/CapturaRapida.vue'
import TourGuias from './components/TourGuias.vue'
import SelectorPerfil from './components/SelectorPerfil.vue'
import Logo from './components/Logo.vue'
import api from './services/api'
import { useAuth } from './stores/auth'
import { useTema } from './composables/useTema'
import { configurarFormato, usarPorDefecto } from './utils/formato'
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

/**
 * El recorrido se ofrece una vez, la primera vez que se entra con cuenta.
 * No se vuelve a salir solo: si el usuario lo omitio, decidio. Ajustes lo tiene
 * siempre disponible para cuando quiera repasarlo.
 *
 * Siempre arranca en Inicio. Los pasos que señalan la tarjeta de quincena y la
 * de alerta viven en el Dashboard: si se abriera el recorrido desde Ajustes, esos
 * dos pasos no tendrian nada que señalar y se perderian en silencio. Peor: el
 * usuario veria un tour mas corto y pensaria que le faltaba informacion.
 */
/**
 * Mientras el recorrido esta abierto, moverse por la app lo pone en modo
 * tutorial: no se cierra, solo se vuelve a medir el elemento en la pantalla
 * nueva. El usuario decide cuando salir, con un clic fuera.
 */
watch(() => route.path, () => tour.value?.alNavegar())

const tour = ref<InstanceType<typeof TourGuias> | null>(null)

async function abrirTour() {
  modoTutorial.value = false
  if (route.path !== '/inicio') {
    await router.push('/inicio').catch(() => {})
    await new Promise((r) => setTimeout(r, 420))
  }
  tour.value?.abrir()
}
const modoTutorial = ref(false)
function onPedirTour() { void abrirTour() }
/**
 * Ajustes acaba de cambiar el periodo (mes/quincena). App.vue guarda el
 * contexto que usa el tour, asi que sin esto el texto del recorrido seguiria
 * hablando de quincenas a quien acaba de apagarlas.
 */
function onPeriodo(e: Event) {
  ctxPais.value.usaQuincena = Boolean((e as CustomEvent<boolean>).detail)
}
/**
 * Ayuda contextual: abre el tour en el paso que explica la pantalla actual y no
 * cambia de ruta, al contrario que abrirTour(), que siempre arranca en Inicio.
 */
function abrirAyuda() { tour.value?.abrirEnRuta(route.path) }
onMounted(() => {
  useTema().init()
  window.addEventListener('ctd:sesion-cerrada', onSesionCerrada)
  window.addEventListener('ctd:ver-tour', onPedirTour)
window.addEventListener('ctd:periodo', onPeriodo)
  document.addEventListener('visibilitychange', onVisible)
  void validarSesion(true)
  // El formato de dinero y numeros se fija desde la sesion, no desde la moneda
  // suelta: con es-CO fijo un usuario de Estados Unidos veia 1.234.567.
  if (authed.value) {
    api.get('/auth/me').then(({ data }) => {
      configurarFormato(data.pais, data.moneda)
      // El texto del recorrido depende del pais: en uno sin quincena, el paso
      // "tu quincena" seria mentira.
      ctxPais.value = { pais: data.pais, nombre: data.pais_nombre, usaQuincena: data.usa_quincena }
    }).catch(() => usarPorDefecto())
  } else {
    usarPorDefecto()
  }
  if (authed.value && tour.value?.pendiente()) {
    setTimeout(() => void abrirTour(), 900)
  }
})
const ctxPais = ref<{ pais: string; nombre: string; usaQuincena: boolean }>({
  pais: 'CO', nombre: 'Colombia', usaQuincena: true,
})
onUnmounted(() => {
  window.removeEventListener('ctd:sesion-cerrada', onSesionCerrada)
  window.removeEventListener('ctd:ver-tour', onPedirTour)
window.removeEventListener('ctd:periodo', onPeriodo)
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

/* Escritorio: la cabecera sigue al contenido y se corre a un lado de la
   columna de navegación. Va aquí y no en tokens.css porque la regla base de
   .topbar está en este mismo bloque y, a igual especificidad, gana la que
   aparece después. */
@media (min-width: 1000px) {
  .topbar {
    max-width: 1080px; margin: 0 auto 0 216px; padding: 16px 24px 0;
    display: flex; align-items: center; gap: 10px;
    position: sticky; top: 0; z-index: 15;
    background: var(--bg);
  }
  /* Las pantallas publicas (landing, login, registro) arrancan con un bloque a
     sangre y no tienen columna lateral. Sin esto heredan el margen de 216px
     reservado para el sidebar, que descentra el contenido y deja la barra
     clara pegada encima del hero.

     Doble clase a proposito: tokens.css se importa DESPUES de App.vue, asi que
     su `.topbar` (0,1,0) le gana a un `.topbar--public` de una sola clase y
     las correcciones publicas no se aplicaban. */
  .topbar.topbar--public {
    max-width: none; margin: 0; padding: 16px 24px;
    position: static; z-index: auto;
    background: transparent;
  }
  /* Mismo desfase en .page: el offset del sidebar no aplica fuera de la app. */
  .app-public .page { margin-left: auto; }
  .app-public .topbar { margin-left: auto; }
}
</style>
