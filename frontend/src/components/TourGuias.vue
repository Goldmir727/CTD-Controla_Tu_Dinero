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
import { PASOS, type Paso } from '../tour/pasos'

const CLAVE = 'ctd-tour-v3'
const abierto = ref(false)
const indice = ref(0)
const caja = ref<{ top: number; left: number; width: number; height: number } | null>(null)
const paso = computed<Paso | null>(() => PASOS[indice.value] ?? null)
const esUltimo = computed(() => indice.value === PASOS.length - 1)

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
  void medir()
}
function cerrar() { abierto.value = false; caja.value = null }
function saltar() { marcar('omitido'); cerrar() }
function terminar() { marcar('completado'); cerrar() }

function avanzar() {
  if (esUltimo.value) return terminar()
  indice.value += 1
  void medir()
}
function atras() {
  if (indice.value > 0) { indice.value -= 1; void medir() }
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

/** Ubica el elemento y pone la tarjeta al lado pedido sin salirse. */
async function medir() {
  await nextTick()
  const p = paso.value
  if (!p?.selector) { caja.value = null; return }
  const el = primerVisible(p.selector)
  if (!el) {
    // No hay nada que señalar en esta pantalla: se pasa al siguiente paso.
    if (!esUltimo.value) { indice.value += 1; return medir() }
    caja.value = null
    return
  }
  el.scrollIntoView({ block: 'center', behavior: 'smooth' })
  await new Promise((r) => setTimeout(r, 260))
  const r = el.getBoundingClientRect()
  if (r.width === 0 && r.height === 0) { caja.value = null; return }
  caja.value = { top: r.top, left: r.left, width: r.width, height: r.height }
}

/** La tarjeta nunca debe salirse de la ventana. */
const tarjeta = computed(() => {
  const c = caja.value
  const ancho = 340
  const alto = 210
  if (!c) return { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }
  const margen = 14
  let top = c.top + c.height + margen
  if (top + alto > window.innerHeight - margen) {
    top = c.top - alto - margen
    if (top < margen) top = Math.max(margen, window.innerHeight - alto - margen)
  }
  let left = c.left + c.width / 2 - ancho / 2
  left = Math.max(margen, Math.min(left, window.innerWidth - ancho - margen))
  return { top: `${top}px`, left: `${left}px`, transform: 'none', width: `${ancho}px` }
})

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
  if (e.key === 'Escape') saltar()
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

watch(indice, () => void medir())

defineExpose({ abrir, pendiente, cerrar })
</script>

<template>
  <div v-if="abierto && paso" class="tour">
    <div class="tour-backdrop" @click="saltar"></div>

    <div
      v-if="agujero"
      class="tour-agujero"
      :style="agujero"
      aria-hidden="true"
    ></div>

    <div class="tour-card" :style="tarjeta" role="dialog" aria-modal="true">
      <p class="tour-contador">
        {{ indice + 1 }} de {{ PASOS.length }}
        <span v-if="agujero" class="tour-flecha"></span>
      </p>
      <h3>{{ paso.titulo }}</h3>
      <p class="tour-texto">{{ paso.texto }}</p>

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
      <p class="tour-pie">También con las flechas del teclado. Esc para omitir.</p>
    </div>
  </div>
</template>

<style scoped>
.tour { position: fixed; inset: 0; z-index: 90; }
.tour-backdrop { position: absolute; inset: 0; }

/* El agujero: un div del tamaño del elemento con una sombra que tapa todo lo
   demás. El puntero se desactiva para no comerse los clics de la tarjeta. */
.tour-agujero {
  position: fixed;
  border-radius: 14px;
  box-shadow: 0 0 0 9999px rgba(5, 11, 59, .72);
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
.tour-contador {
  margin: 0 0 6px; font-size: 11px; letter-spacing: .1em;
  color: var(--mint-dark); font-weight: 800; text-transform: uppercase;
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
  font-size: 13px; cursor: pointer; padding: 8px 4px;
}
.tour-saltar:hover, .tour-atras:hover { color: var(--ink); }
.tour-sig {
  background: var(--mint); color: var(--navy); border: 0;
  border-radius: 10px; padding: 10px 18px; font-weight: 800; cursor: pointer;
}
.tour-sig:hover { background: var(--mint-dark); }
.tour-pie { margin: 10px 0 0; font-size: 11px; color: var(--ink-soft); opacity: .8; }
.tour-flecha { display: none; }
</style>