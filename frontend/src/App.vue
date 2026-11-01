<template>
<div :class="{ 'app-public': !authed }">
    <header class="topbar" :class="{ 'topbar--public': !authed }">
      <Logo :width="44" />
      <strong>CTD</strong>
      <span style="flex: 1"></span>
      <span data-tour="perfil" style="display:flex"><SelectorPerfil v-if="authed" @cambio="tick++" /></span>
      <button v-if="showHeaderCta" class="btn-primary desktop-only" data-tour="nuevo-movimiento" @click="$router.push('/movimientos/nuevo')">+ Nuevo movimiento</button>
      <button v-if="isLanding && !authed" class="btn-ghost" @click="$router.push('/login')">Entrar</button>
      <button v-if="authed" class="gear" @click="abrirAyuda" aria-label="Ayuda" title="Ayuda"><i class="bi bi-question-lg"></i></button>
      <button v-if="authed" class="gear" data-tour="ajustes" @click="$router.push('/config')" aria-label="Ajustes"><i class="bi bi-gear"></i></button>
    </header>
    <!-- Sin red el usuario necesita dos datos: que esta sin red y que SI puede
         seguir registrando. Un aviso generico de "sin conexion" dejaba la duda
         de si algo se habia perdido. -->
    <div v-if="authed && (!offline.conectado || offline.hayPendientes)"
         class="offline-bar" :class="offline.conectado ? 'offline-bar--sync' : ''"
         role="status" aria-live="polite">
      <i class="bi" :class="offline.conectado ? 'bi-cloud-arrow-up' : 'bi-wifi-off'" aria-hidden="true"></i>
      <p v-if="!offline.conectado">
        <strong>Sin conexión.</strong>
        Puedes registrar movimientos y fijos: se guardan en este dispositivo y se envían solos al volver la red.
        Reportes, agenda, análisis y asesor necesitan internet.
      </p>
      <p v-else>
        <strong>{{ offline.sincronizando ? 'Enviando cambios…' : textoPendientes }}</strong>
        <span v-if="offline.ultimoError"> · {{ offline.ultimoError }}</span>
      </p>
      <button v-if="offline.conectado && !offline.sincronizando"
              class="offline-bar__btn" @click="offline.sincronizar()">Reintentar</button>
    </div>
    <router-view :key="tick" />
    <CapturaRapida ref="captura" @guardado="refrescarTrasCaptura" />
    <TourGuias ref="tour" :pais="ctxPais" />
    <InstallPrompt v-if="authed" />
    <UpdateBanner />
    <CookieBanner />
    <ConsentBanner />
    <ConfirmDialog />
    <ToastStack />
    <!-- Un solo panel para las tres formas de registrar. Antes la captura por
         voz vivía en una pastilla flotante aparte: dos acciones primarias
         peleando por el mismo pulgar. -->
    <div v-if="fan" class="fan-backdrop" @click.self="fan = false">
      <div ref="fanEl" class="fan" role="dialog" aria-modal="true" aria-labelledby="fan-titulo" @click.stop>
        <p id="fan-titulo" class="fan-titulo">Registrar</p>
        <!-- La captura por voz/texto la resuelve el servidor: sin red no puede
             funcionar. El ingreso manual de abajo si, y no depende de la red. -->
        <button class="fan-captura" data-autofocus :disabled="!offline.conectado"
                :aria-describedby="!offline.conectado ? 'fan-sin-red' : undefined"
                @click="pedirCaptura">
          <i class="bi bi-magic" aria-hidden="true"></i> Dictar o escribir
        </button>
        <p v-if="!offline.conectado" id="fan-sin-red" class="fan-nota">
          Sin conexión: dictar necesita internet. Ingresa el monto a mano abajo y se guarda igual.
        </p>
        <div class="fan-tipos">
          <button @click="go('ingreso')">+ Ingreso</button>
          <button @click="go('gasto')">− Gasto</button>
        </div>
      </div>
    </div>
    <button v-if="showFab" class="fab" data-tour="captura" aria-label="Registrar movimiento" @click="fan = true">+</button>
    <nav v-if="authed" class="bottom-nav" data-tour="nav" aria-label="Navegación principal">
      <div class="nav-side">
        <router-link to="/inicio"><i class="bi bi-house" aria-hidden="true"></i><span>Inicio</span></router-link>
        <router-link to="/movimientos" aria-label="Movimientos"><i class="bi bi-list-ul" aria-hidden="true"></i><span>Movs</span></router-link>
        <router-link to="/agenda" aria-label="Calendario"><i class="bi bi-calendar3" aria-hidden="true"></i><span>Agenda</span></router-link>
      </div>
      <span class="fab-gap"></span>
      <div class="nav-side">
        <router-link to="/plan"><i class="bi bi-bullseye" aria-hidden="true"></i><span>Plan</span></router-link>
        <router-link to="/analisis" aria-label="Análisis y datos"><i class="bi bi-bar-chart" aria-hidden="true"></i><span>Datos</span></router-link>
        <router-link to="/asesor"><i class="bi bi-chat-dots" aria-hidden="true"></i><span>Asesor</span></router-link>
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
import ConfirmDialog from './components/ConfirmDialog.vue'
import ToastStack from './components/ToastStack.vue'
import CapturaRapida from './components/CapturaRapida.vue'
import TourGuias from './components/TourGuias.vue'
import SelectorPerfil from './components/SelectorPerfil.vue'
import Logo from './components/Logo.vue'
import api from './services/api'
import { useAuth } from './stores/auth'
import { useTema } from './composables/useTema'
import { useDialog } from './composables/useDialog'
import { responderConfirm } from './composables/useConfirm'
import { configurarFormato, usarPorDefecto } from './utils/formato'
import { useOffline } from './stores/offline'
import {
  listarCategorias, listarCuentas, listarMetodosPago, listarMovimientos, listarPerfiles, listarRecurrentes,
} from './services/repository'
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
const fanEl = ref<HTMLElement | null>(null)
const captura = ref<InstanceType<typeof CapturaRapida> | null>(null)
useDialog(computed(() => fan.value), fanEl, () => { fan.value = false })
const offline = useOffline()
const textoPendientes = computed(() => offline.pendientes === 1
  ? '1 cambio sin enviar'
  : `${offline.pendientes} cambios sin enviar`)
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
  } catch (e) {
    // Sin red el error no dice nada sobre la sesion. Antes cualquier fallo
    // borraba los tokens: al abrir la app en el bus el usuario aparecia
    // desconectado de su cuenta y no podia registrar nada.
    const status = (e as { response?: { status?: number } }).response?.status
    if (!navigator.onLine || !status) return
    if (status === 401 || status === 403) {
      auth.clear()
      aLanding()
    }
  }
}

function onSesionCerrada() {
  // Cualquier confirmación pendiente se cancela: si no, quedaría un diálogo
  // de borrado abierto sobre la landing, esperando una respuesta imposible.
  responderConfirm(false)
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
/**
 * Con la app ya abierta, entrar a la cuenta no vuelve a montar App.vue: sin este
 * watch la copia offline no se creaba hasta visitar Movimientos, y quien se
 * quedaba sin red justo despues del login se encontraba el formulario sin
 * cuentas ni categorias.
 */
watch(() => auth.isAuthed, (entro) => { if (entro) void precargar() })

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
  window.addEventListener('online', precargar)
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
  void precargar()
})

/**
 * Deja copia en IndexedDB de lo que hace falta para registrar sin red: cuentas,
 * categorias, metodos, el historial del perfil activo y los fijos. Se hace al
 * entrar y no al abrir el formulario porque la conexion se suele perder despues
 * de haber usado la app, no antes.
 */
async function precargar() {
  if (!auth.isAuthed || !navigator.onLine) {
    void offline.refreshPendientes()
    return
  }
  try {
    const perfiles = await listarPerfiles()
    const guardado = localStorage.getItem('ctd-perfil') ?? ''
    const activo = perfiles.find((p) => p.id === guardado)
      ?? perfiles.find((p) => p.principal) ?? perfiles[0]
    await Promise.all([
      listarCategorias(),
      listarCuentas(),
      listarMetodosPago(),
      listarRecurrentes(activo?.id),
      listarMovimientos(activo?.id),
    ])
  } catch { /* si algo falla, la copia anterior sigue sirviendo */ }
  void offline.refreshPendientes()
}
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
  window.removeEventListener('online', precargar)
})
// Acción global solo donde tiene sentido: Plan tiene sus propios CTA (presupuesto/meta).
const showHeaderCta = computed(() => authed.value && ['/inicio', '/movimientos'].includes(route.path))
const showFab = computed(() => authed.value && !['/', '/login', '/registro', '/onboarding', '/2fa', '/movimientos/nuevo'].includes(route.path))
function go(tipo: string) { fan.value = false; router.push({ path: '/movimientos/nuevo', query: { tipo } }) }
function pedirCaptura() { fan.value = false; captura.value?.abrir() }
</script>

<style>
.topbar {
  display: flex; align-items: center; gap: 8px; max-width: 720px; margin: 0 auto;
  padding: calc(12px + var(--safe-top)) 16px 12px;
}
.gear {
  background: none; border: 1px solid var(--line); border-radius: 12px;
  width: 44px; height: 44px; display: inline-flex; align-items: center; justify-content: center;
  font-size: 18px; cursor: pointer; flex: none;
}
.gear:focus-visible { outline: none; box-shadow: 0 0 0 3px rgba(0, 255, 171, 0.25); }
/* Aviso de estado de red: va pegado a la cabecera porque aplica a toda la app. */
.offline-bar {
  display: flex; align-items: center; gap: 10px;
  max-width: 720px; margin: 0 auto;
  padding: 10px 14px 12px;
  font-size: 12.5px; line-height: 1.4;
  color: var(--warning-text);
}
.offline-bar i { font-size: 18px; flex: none; color: var(--warning); }
.offline-bar p { margin: 0; flex: 1; }
.offline-bar strong { font-weight: 800; }
.offline-bar--sync { color: var(--ink-soft); }
.offline-bar--sync i { color: var(--mint-text); }
.offline-bar__btn {
  flex: none; min-height: 36px; padding: 0 12px;
  border: 1px solid var(--line); border-radius: 10px;
  background: var(--surface); color: var(--ink); font: 700 12px var(--font);
  cursor: pointer;
}
.offline-bar__btn:focus-visible { outline: none; box-shadow: 0 0 0 3px rgba(0, 255, 171, 0.25); }
.fan-nota { margin: 0; font-size: 12px; color: var(--ink-soft); }
.fan-captura:disabled { opacity: .5; cursor: not-allowed; }
@media (min-width: 1000px) {
  .offline-bar { max-width: 1080px; margin: 8px auto 0 216px; }
  .app-public .offline-bar { margin-left: auto; }
}
/* En un móvil de 360px el logo + CTD + perfil + dos botones no caben: el
   wordmark es lo primero que se puede quitar sin perder navegación. */
@media (max-width: 380px) { .topbar > strong { display: none; } }
/* Única acción primaria por contexto: FAB solo móvil, botón header solo escritorio */
/* `.topbar .desktop-only` y no `.desktop-only`: tokens.css se importa después
   y su `.btn-primary { display: inline-flex }` (misma especificidad) volvía a
   mostrar este botón en móvil, robando 132px y desbordando la cabecera. */
@media (max-width: 899px) { .topbar .desktop-only { display: none; } }
@media (min-width: 900px) { .fab { display: none; } }
.fan-backdrop {
  position: fixed; inset: 0; background: rgba(5, 11, 59, .55); z-index: var(--z-sheet);
  display: flex; align-items: flex-end; justify-content: center;
  padding: 12px; padding-bottom: calc(12px + var(--safe-bottom));
}
.fan {
  width: 100%; max-width: 480px; display: grid; gap: 10px;
  background: var(--surface); color: var(--ink);
  border-radius: 20px; padding: 16px; box-shadow: var(--shadow);
}
.fan-titulo { margin: 0 0 2px; font-size: 12px; letter-spacing: .12em; font-weight: 700; color: var(--ink-soft); }
.fan-captura {
  min-height: 52px; border: 0; border-radius: 14px; cursor: pointer;
  background: var(--mint); color: var(--navy); font: 800 15px var(--font);
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
}
.fan-tipos { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.fan-tipos button {
  background: var(--navy); color: #fff; border: 1px solid var(--mint); border-radius: 14px;
  padding: 12px; min-height: 52px; font-weight: 700; cursor: pointer;
}
.fan button:focus-visible { outline: none; box-shadow: 0 0 0 3px rgba(0, 255, 171, .35); }

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
