<script setup lang="ts">
/**
 * Recorrido guiado: un reflector sobre el elemento + una tarjeta que explica.
 *
 * El agujero se hace con un box-shadow gigante en vez de recortar el overlay:
 * es menos codigo, no depende de masking ni de librerias, y se puede animar
 * siguiendo el elemento cuando este se mueve.
 *
 * Un paso cuyo selector no existe (porque el usuario esta en otra pantalla) se
 * salta solo en vez de romper: el recorrido no puede ser la razon de que la app
 * se vea rara.
 */
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { indiceParaRuta, pasosPara, type ContextoPais, type Paso } from '../tour/pasos'

const CLAVE = 'ctd-tour-v4'
const abierto = ref(false)
const indice = ref(0)
const caja = ref<{ top: number; left: number; width: number; height: number } | null>(null)
const ctx = ref<ContextoPais>({ pais: 'CO', nombre: 'Colombia', usaQuincena: true })

/** Los pasos dependen del pais: en uno sin quincena el texto de ese paso seria mentira. */
const PASOS = computed(() => pasosPara(ctx.value))
const paso = computed<Paso | null>(() => PASOS.value[indice.value] ?? null)
const esUltimo = computed(() => indice.value === PASOS.value.length - 1)
const textoPaso = computed(() => {
  const t = paso.value?.texto
  return typeof t === 'function' ? t(ctx.value) : (t ?? '')
})

/** Omitir es una decision, no un fallo: se guarda igual que terminarlo. */
function marcar(nombre: string) {
  try {
    localStorage.setItem(CLAVE, JSON.stringify({ visto: true, ultima: nombre, ts: Date.now() }))
  } catch { /* modo privado: se pierde y se vuelve a mostrar */ }
}
const visto = () => {
  try { return !!JSON.parse(localStorage.getItem(CLAVE) || '{}').visto } catch { return false }
}
const pendiente = () => !visto()

function abrir(desde = 0) {
  indice.value = desde
  abierto.value = true
  armado.value = false
  void medir()
}
function cerrar() {
  abierto.value = false
  armado.value = false
  modoTutorial.value = false
  caja.value = null
  // Al cerrar se olvida por donde iba: la proxima vez arranca en el paso 1.
  indice.value = 0
}
function saltar() { marcar('omitido'); cerrar() }
function terminar() { marcar('completado'); cerrar() }
/**
 * Boton Cerrar. Marca el recorrido como descartado (no completado) para que no
 * se reabra solo en cada carga, y `cerrar()` reinicia el indice: si el usuario
 * lo vuelve a lanzar desde Ajustes arranca en el paso 1.
 */
function cerrarTour() { marcar('cerrado'); cerrar() }

function avanzar() {
  if (esUltimo.value) return terminar()
  indice.value += 1
  void medir()
}
/**
 * Atras NUNCA salta. Sin el salto automatico, volver a un paso cuyo elemento no
 * esta (la alerta, que solo se ve cuando hay alertas) lo muestra centrado, sin
 * Spotlight, en lugar de rebotar al siguiente y dejar el boton sin efecto.
 */
function atras() {
  if (indice.value > 0) { indice.value -= 1; void medir() }
}

/**
 * Modo tutorial: mientras esta activo, moverse por la app NO cierra el
 * recorrido, y el elemento resaltado se vuelve a medir en cada cambio de
 * pantalla. Si no, el tour se quedaria apuntando a un elemento que ya no existe.
 *
 * Se sale del modo tutorial cuando el usuario hace clic FUERA de la tarjeta y
 * del elemento señalado (navegar, explorar, cerrar). Ese es el gesto de
 * "ya entendi, dejame usar la app", y por eso lo respeta sin preguntar.
 */
const modoTutorial = ref(false)
/** El proximo clic fuera se gasta en navegar; el siguiente ya cierra el tour. */
const armado = ref(false)

/** Se llama desde App.vue cuando cambia la ruta mientras el tour esta abierto. */
function alNavegar() {
  if (!abierto.value) return
  modoTutorial.value = true
  armado.value = false
  void medir()
}

/**
 * Primer elemento VISIBLE que coincide con el selector.
 *
 * Hace falta porque hay dos formas de capturar y solo una existe a la vez: el
 * boton flotante se oculta en escritorio (lo tapa el boton de la cabecera) y el
 * de la cabecera se oculta en movil. Si se tomara el primero que aparezca en el
 * DOM, en uno de los dos casos se apuntaria a algo con tamano cero.
 */
function primerVisible(sel: string): HTMLElement | null {
  for (const el of Array.from(document.querySelectorAll(sel))) {
    const r = el.getBoundingClientRect()
    if (r.width > 0 && r.height > 0) return el as HTMLElement
  }
  return null
}

/**
 * Ubica el elemento y pone la tarjeta al lado pedido sin salirse.
 *
 * En modo tutorial NO se salta un paso cuyo selector no aparece: si el usuario
 * esta mirando otra pantalla, se queda en el paso y espera a que vuelva. Saltarse
 * perderia la leccion sin que el usuario la haya visto.
 */
async function medir() {
  await nextTick()
  const p = paso.value
  if (!p?.selector) { caja.value = null; return }
  const el = primerVisible(p.selector)
  // Nunca se salta un paso, ni hacia adelante ni hacia atras.
  //
  // Antes, si el elemento no estaba (la alerta solo aparece cuando hay alertas),
  // `medir` avanzaba solo. Eso rompia el recorrido de dos maneras: el contador
  // daba un salto (3 -> 5) y, al volver con Atras, el paso se saltaba de nuevo y
  // el boton no hacia nada. Ahora el paso siempre se muestra; si su elemento no
  // esta, la tarjeta sale centrada sin spotlight, que es lo mismo que hace el
  // modo tutorial.
  if (!el) { caja.value = null; return }
  el.scrollIntoView({ block: 'center', behavior: 'smooth' })
  await new Promise((r) => setTimeout(r, 260))
  const r = el.getBoundingClientRect()
  if (r.width === 0 && r.height === 0) { caja.value = null; return }
  caja.value = { top: r.top, left: r.left, width: r.width, height: r.height }
}

/**
 * La tarjeta es ESTATICA: siempre centrada, sin seguir al elemento resaltado.
 * Antes se colocaba pegada al blanco y en movil caia encima de la barra de
 * navegacion o del boton flotante, tapando el boton que el paso queria
 * señalar. Centrada nunca se cruza con la barra inferior, que vive en el borde.
 */
const tarjeta = computed(() => ({
  top: '50%',
  left: '50%',
  transform: 'translate(-50%, -50%)',
  width: 'min(340px, calc(100vw - 32px))',
}))

/** El recorte queda un poco mas grande que el elemento para que se vea. */
const agujero = computed(() => {
  const c = caja.value
  if (!c) return null
  const p = 8
  return {
    top: `${c.top - p}px`, left: `${c.left - p}px`,
    width: `${c.width + p * 2}px`, height: `${c.height + p * 2}px`,
  }
})

function alTeclado(e: KeyboardEvent) {
  if (!abierto.value) return
  // Esc ya no cierra: el modal es estatico y la unica salida es "Cerrar".
  if (e.key === 'ArrowRight') avanzar()
  if (e.key === 'ArrowLeft') atras()
}
const recentrar = () => { if (abierto.value) void medir() }

onMounted(() => {
  window.addEventListener('resize', recentrar)
  window.addEventListener('scroll', recentrar, true)
  window.addEventListener('keydown', alTeclado)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', recentrar)
  window.removeEventListener('scroll', recentrar, true)
  window.removeEventListener('keydown', alTeclado)
})

// Antes de los watches: el getter de la linea siguiente corre de inmediato y
// con `const props` declarado mas abajo queda en TDZ (ReferenceError).
const props = defineProps<{ pais?: ContextoPais | null }>()

watch(indice, () => void medir())

/**
 * El pais llega desde App.vue porque ahi ya se sabe de la sesion. Se mira en
 * watch y no solo al montar: el tour puede abrirse antes de que /auth/me
 * responda, y con un solo watch se perderia el texto de quincena.
 */
watch(() => props.pais, (p) => {
  if (p && p.pais) ctx.value = p
  if (abierto.value) void medir()
}, { deep: true })

/**
 * Ayuda contextual: abre el tour en el paso que explica la pantalla actual, sin
 * moverse de ruta. Es lo que dispara el boton "?" de la cabecera.
 */
function abrirEnRuta(ruta: string) {
  abrir(indiceParaRuta(PASOS.value, ruta))
}

defineExpose({ abrir, abrirEnRuta, pendiente, cerrar, alNavegar })
</script>

<template>
  <div v-if="abierto && paso" class="tour" :class="{ tutorial: modoTutorial }">
    <!-- Fondo opaco e inerte: el modal es estatico y NO se cierra al hacer clic
         fuera. La unica salida es el boton Cerrar. -->
    <div class="tour-backdrop"></div>

    <div
      v-if="agujero"
      class="tour-agujero"
      :style="agujero"
      aria-hidden="true"
    ></div>

    <div class="tour-card" :style="tarjeta" role="dialog" aria-modal="true">
      <button class="tour-cerrar" @click="cerrarTour" aria-label="Cerrar el recorrido">Cerrar</button>
      <p class="tour-contador">
        {{ indice + 1 }} de {{ PASOS.length }}
        <span v-if="agujero" class="tour-flecha"></span>
      </p>
      <h3>{{ paso.titulo }}</h3>
      <p class="tour-texto">{{ textoPaso }}</p>

      <div class="tour-puntos" aria-hidden="true">
        <span
          v-for="(p, i) in PASOS"
          :key="i"
          :class="['punto', { on: i === indice, hecho: i < indice }]"
        ></span>
      </div>

      <div class="tour-botones">
        <button class="tour-saltar" @click="saltar">Omitir</button>
        <span style="flex: 1"></span>
        <button v-if="indice > 0" class="tour-atras" @click="atras">Atrás</button>
        <button class="tour-sig" @click="avanzar">
          {{ esUltimo ? 'Listo' : 'Siguiente' }}
        </button>
      </div>
      <p class="tour-pie">
        <template v-if="modoTutorial">
          Estas en otra pantalla: el recorrido espera aqui. Usa Cerrar para salir.
        </template>
        <template v-else>
          También con las flechas del teclado.
        </template>
      </p>
    </div>
  </div>
</template>

<style scoped>
.tour { position: fixed; inset: 0; z-index: var(--z-tour); }
/* El fondo es el que oscurece y el que bloquea. Antes el oscurecido venia del
   box-shadow del agujero, asi que cuando un paso no encontraba su elemento
   (por ejemplo la alerta, que solo existe a veces) el modal quedaba sin fondo y
   la app de detras seguia siendo clicable. */
.tour-backdrop { position: absolute; inset: 0; background: rgba(5, 11, 59, .72); }
.tour.tutorial .tour-agujero { outline-color: var(--mint); }

/* Resalta el elemento señalado por encima del fondo oscurecido. */
.tour-agujero {
  position: fixed;
  border-radius: 14px;
  background: rgba(0, 255, 171, .10);
  pointer-events: none;
  transition: top .25s ease, left .25s ease, width .25s ease, height .25s ease;
  outline: 2px solid var(--mint);
  outline-offset: 2px;
}

.tour-card {
  position: fixed;
  background: var(--surface);
  color: var(--ink);
  border-radius: 16px;
  padding: 18px;
  box-shadow: 0 18px 50px rgba(5, 11, 59, .35);
  border: 1px solid var(--line);
  z-index: 1;
}
/* Unica salida del modal. */
.tour-cerrar {
  position: absolute; top: 8px; right: 8px;
  min-height: 44px; min-width: 64px;
  display: inline-flex; align-items: center; justify-content: center;
  background: none; border: 1px solid var(--line); border-radius: 99px;
  color: var(--ink-soft); font-size: 12px; font-weight: 700;
  padding: 5px 12px; cursor: pointer;
}
.tour-cerrar:hover { color: var(--ink); border-color: var(--mint); }
.tour-contador {
  margin: 0 0 6px; padding-right: 64px; font-size: 11px; letter-spacing: .1em;
  color: var(--mint-text); font-weight: 800; text-transform: uppercase;
}
.tour-card h3 { margin: 0 0 8px; font-size: 17px; line-height: 1.25; }
.tour-texto { margin: 0 0 14px; font-size: 14px; line-height: 1.5; color: var(--ink-soft); }

.tour-puntos { display: flex; gap: 5px; margin-bottom: 14px; }
.punto { width: 6px; height: 6px; border-radius: 99px; background: var(--line); }
.punto.hecho { background: var(--mint-dim); }
.punto.on { background: var(--mint-dark); width: 18px; }

.tour-botones { display: flex; align-items: center; gap: 8px; }
.tour-saltar, .tour-atras {
  background: none; border: 0; color: var(--ink-soft);
  font-size: 13px; cursor: pointer; padding: 8px 4px; min-height: 44px;
}
.tour-saltar:hover, .tour-atras:hover { color: var(--ink); }
.tour-sig {
  background: var(--mint); color: var(--navy); border: 0;
  border-radius: 10px; padding: 10px 18px; min-height: 44px; font-weight: 800; cursor: pointer;
}
.tour-sig:hover { background: var(--mint-dark); }
.tour-pie { margin: 10px 0 0; font-size: 12px; color: var(--ink-soft); }
.tour-flecha { display: none; }
</style>