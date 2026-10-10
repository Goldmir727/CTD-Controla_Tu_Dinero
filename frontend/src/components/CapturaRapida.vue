<script setup lang="ts">
/** Captura rápida: escribir (o dictar) una frase y confirmar los movimientos.
 *
 *  Decisiones de producto que implementa:
 *  - Siempre confirma con un toque. NUNCA guarda solo, porque el modelo se equivoca.
 *  - Si el monto NO estaba en el texto, se pide confirmarlo a mano (lo decide el
 *    backend con requiere_confirmacion_monto) y se marca en amarillo.
 *  - Atajo "guardar siempre" para quien ya confia: salta la hoja solo cuando NO
 *    hay montos dudosos.
 *  - La app no guarda nada hasta que el usuario toca Guardar. */
import { computed, ref } from 'vue'
import api from '../services/api'
import { dinero, numero } from '../utils/formato'
import { useAuth } from '../stores/auth'

type Coincidencia = {
  id: string
  nombre: string
  tipo: 'gasto' | 'ingreso'
  monto: number
  dia: number
  frecuencia: string
  confianza: number
  motivo: string
}
type Mov = {
  ix: number
  tipo: 'gasto' | 'ingreso'
  monto: number
  falta_monto: boolean
  requiere_confirmacion_monto: boolean
  monto_explicito: boolean
  categoria_id: string | null
  categoria: string | null
  descripcion: string
  metodo_id: string | null
  metodo: string | null
  fecha: string
  fijo: boolean
  /** Fijos declarados que PODRIAN ser este movimiento. La UI pregunta. */
  coincidencias?: Coincidencia[]
  /** Que eligio el usuario: un id de fijo, 'nuevo' o null (nada). */
  eleccion?: string | null
}
type Propuesta = {
  captura_id: string
  /** El texto original, tal cual lo mando el usuario. */
  texto: string
  movimientos: Mov[]
  avisos: string[]
  requiere_confirmacion_monto: boolean
  total: number
  cuenta_por_defecto: string | null
  opciones: {
    categorias: { id: string; nombre: string; tipo: string }[]
    cuentas: { id: string; nombre: string; tipo: string }[]
    metodos: { id: string; nombre: string }[]
  }
}

const emit = defineEmits<{ (e: 'guardado', n: number): void }>()

const abierto = ref(false)
const texto = ref('')
const cargando = ref(false)
const error = ref('')
const propuesta = ref<Propuesta | null>(null)
const guardarSiempre = ref(localStorage.getItem('ctd-captura-auto') === '1')
const cuota = ref<{ queda: number; limite: number } | null>(null)

const authed = computed(() => useAuth().isAuthed)
const hayDudosos = computed(() => propuesta.value?.movimientos.some((m) => m.requiere_confirmacion_monto) ?? false)
const total = computed(() =>
  (propuesta.value?.movimientos ?? [])
    .filter((m) => m.tipo === 'gasto')
    .reduce((s, m) => s + (Number(m.monto) || 0), 0)
)

// --- Nota de voz ---
// MediaRecorder es la unica forma de grabar en el navegador sin permisos raros.
// Android Chrome produce webm/opus, que es justo lo que acepta Whisper.
const grabando = ref(false)
const segundos = ref(0)
let grabador: MediaRecorder | null = null
let flujos: MediaStream | null = null
let crono: number | null = null

const MAX_SEGUNDOS = 30

function soportado(): boolean {
  return !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== 'undefined'
}

async function iniciarVoz() {
  error.value = ''
  if (!soportado()) {
    error.value = 'Este navegador no permite grabar. Escribe la frase, funciona igual.'
    return
  }
  try {
    flujos = await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch (e) {
    // NoNegado es el caso normal; no se puede forzar desde la web.
    const nombre = (e as { name?: string }).name
    error.value = nombre === 'NotAllowedError'
      ? 'Sin permiso para el micrófono. Habilítalo en el candado de la barra de dirección.'
      : 'No pude abrir el micrófono. Revisa que otro app no lo esté usando.'
    return
  }
  // El navegador elige el contenedor; le damos pista de webm si puede.
  const opciones = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
    .find((t) => MediaRecorder.isTypeSupported?.(t))
  grabador = new MediaRecorder(flujos, opciones ? { mimeType: opciones } : undefined)
  const trozos: BlobPart[] = []
  grabador.ondataavailable = (ev) => { if (ev.data.size) trozos.push(ev.data) }
  grabador.onstop = () => void enviarAudio(new Blob(trozos, { type: grabador?.mimeType || 'audio/webm' }))
  grabador.start()
  grabando.value = true
  segundos.value = 0
  crono = window.setInterval(() => {
    segundos.value += 1
    if (segundos.value >= MAX_SEGUNDOS) detenerVoz()
  }, 1000)
}

function detenerVoz() {
  if (crono) { clearInterval(crono); crono = null }
  grabando.value = false
  if (grabador && grabador.state !== 'inactive') grabador.stop()
  liberarMicrofono()
}

function liberarMicrofono() {
  // Si no se sueltan los tracks, el indicador rojo del microfono sigue encendido.
  flujos?.getTracks().forEach((t) => t.stop())
  flujos = null
}

async function enviarAudio(blob: Blob) {
  if (!blob.size) { error.value = 'No se grabó nada.'; return }
  if (blob.size > 8_000_000) { error.value = 'La nota quedó muy larga. Graba máximo 30 segundos.'; return }
  cargando.value = true
  error.value = ''
  propuesta.value = null
  try {
    const fd = new FormData()
    fd.append('audio', blob, 'nota.webm')
    const { data } = await api.post<Propuesta>('/captura/voz', fd)
    texto.value = data.texto
    propuesta.value = data
    if (guardarSiempre.value && !data.requiere_confirmacion_monto) {
      await confirmar()
      return
    }
    void cargarUso()
  } catch (e: unknown) {
    const r = (e as { response?: { status?: number; data?: { detail?: string } } }).response
    error.value = r?.status === 429
      ? 'Llegaste al límite de capturas de hoy.'
      : (r?.data?.detail ?? 'No pude procesar el audio. Intenta de nuevo.')
    void cargarUso()
  } finally {
    cargando.value = false
  }
}

function abrir() {
  abierto.value = true
  error.value = ''
  void cargarUso()
}

function cerrar() {
  abierto.value = false
  propuesta.value = null
  texto.value = ''
  error.value = ''
  // Si el usuario cierra mientras graba, el microfono se queda encendido si no
  // se suelta aqui: el indicador rojo del navegador no se apaga nunca.
  if (grabando.value) detenerVoz()
}

async function cargarUso() {
  try {
    const { data } = await api.get('/captura/uso')
    cuota.value = { queda: data.queda, limite: data.limite }
  } catch { /* sin cuota no se bloquea nada */ }
}

function alternarAuto() {
  guardarSiempre.value = !guardarSiempre.value
  localStorage.setItem('ctd-captura-auto', guardarSiempre.value ? '1' : '0')
}

async function analizar() {
  const t = texto.value.trim()
  if (!t || cargando.value) return
  error.value = ''
  cargando.value = true
  propuesta.value = null
  try {
    const { data } = await api.post<Propuesta>('/captura', { texto: t })
    propuesta.value = data
    // Atajo "guardar siempre": solo si NO hay montos que el modelo dedujo.
    if (guardarSiempre.value && !data.requiere_confirmacion_monto) {
      await confirmar()
      return
    }
    void cargarUso()
  } catch (e: unknown) {
    const r = (e as { response?: { status?: number; data?: { detail?: string } } }).response
    error.value = r?.status === 429
      ? 'Llegaste al límite de capturas de hoy. Se reinicia mañana.'
      : (r?.data?.detail ?? 'No pude analizar esa frase. Intenta de nuevo.')
    void cargarUso()
  } finally {
    cargando.value = false
  }
}

async function confirmar() {
  if (!propuesta.value) return
  const faltantes = propuesta.value.movimientos.filter((m) => !m.categoria_id)
  if (faltantes.length) {
    error.value = 'Elige la categoría de cada movimiento antes de guardar.'
    return
  }
  const sinMonto = propuesta.value.movimientos.filter((m) => !(Number(m.monto) > 0))
  if (sinMonto.length) {
    error.value = 'Falta el monto. La app no adivina cifras: ponlas a mano.'
    return
  }
  cargando.value = true
  error.value = ''
  try {
    const { data } = await api.post('/captura/confirmar', {
      captura_id: propuesta.value.captura_id,
      confirmacion_usuario: true,
      movimientos: propuesta.value.movimientos.map((m) => ({
        tipo: m.tipo,
        monto: Number(m.monto),
        categoria_id: m.categoria_id,
        descripcion: m.descripcion,
        metodo_id: m.metodo_id,
        cuenta_id: propuesta.value?.cuenta_por_defecto,
        fecha: m.fecha,
        fijo: m.fijo,
        // "Sí, es el mismo" -> el id del fijo; "No, es otro" -> crear uno nuevo.
        // Sin respuesta no se manda nada y el gasto se guarda igual: perder el
        // enlace con el plan es mejor que frenar el registro del gasto.
        recurrente_id: m.eleccion && m.eleccion !== 'nuevo' ? m.eleccion : null,
        nuevo_fijo: m.eleccion === 'nuevo'
      }))
    })
    if (data.errores?.length) {
      error.value = `Guardé ${data.creados} y ${data.errores.length} no se pudieron: ${data.errores[0].detalle}`
    }
    if (data.creados > 0) emit('guardado', data.creados)
    cerrar()
    void cargarUso()
  } catch (e: unknown) {
    const r = (e as { response?: { data?: { detail?: string } } }).response
    error.value = r?.data?.detail ?? 'No pude guardar. Intenta de nuevo.'
  } finally {
    cargando.value = false
  }
}
</script>

<template>
  <button v-if="authed && !abierto" class="pill-captura" @click="abrir">
    <i class="bi bi-magic"></i><span>Capturar</span>
  </button>

  <div v-if="abierto" class="cap-backdrop" @click.self="cerrar">
    <div class="cap-sheet">
      <div class="cap-head">
        <strong>{{ propuesta ? 'Revisa antes de guardar' : 'Captura rápida' }}</strong>
        <button class="x" aria-label="Cerrar" @click="cerrar"><i class="bi bi-x-lg"></i></button>
      </div>

      <!-- Paso 1: escribir la frase -->
      <template v-if="!propuesta">
        <p class="sub">
          Escríbelo como lo dirías. Ej: “gasté 18 mil en el almuerzo y 5 mil en un taxi con Nequi”.
        </p>
        <div class="fila-input">
          <input
            v-model="texto"
            class="input"
            placeholder="Gasté 15 lucas en un corrientazo"
            maxlength="500"
            autofocus
            @keyup.enter="analizar"
          />
          <button
            class="mic"
            :class="{ on: grabando }"
            :disabled="cargando"
            :title="grabando ? 'Detener' : 'Grabar nota de voz'"
            @click="grabando ? detenerVoz() : iniciarVoz()"
          >
            <i class="bi" :class="grabando ? 'bi-stop-fill' : 'bi-mic'"></i>
          </button>
        </div>
        <p v-if="grabando" class="grab">
          <span class="punto"></span> Grabando {{ segundos }}s / {{ MAX_SEGUNDOS }}s
        </p>
        <button class="btn-mint full" :disabled="cargando || grabando || !texto.trim()" @click="analizar">
          <span v-if="cargando" class="spinner"></span>
          <template v-else><i class="bi bi-arrow-right"></i> Analizar</template>
        </button>

        <label class="auto">
          <input type="checkbox" :checked="guardarSiempre" @change="alternarAuto" />
          <span>
            <strong>Guardar siempre</strong>
            <em>Guarda solo lo que no tenga monto dudoso. Los dudosos siempre te los pregunto.</em>
          </span>
        </label>

        <p v-if="cuota" class="sub quota">
          Te quedan {{ cuota.queda }} de {{ cuota.limite }} capturas hoy.
        </p>
      </template>

      <!-- Paso 2: revisar y confirmar -->
      <template v-else>
        <p class="sub">Dijiste: “{{ propuesta.texto }}”</p>

        <div v-for="m in propuesta.movimientos" :key="m.ix" class="prop"
             :class="{ dudoso: m.requiere_confirmacion_monto }">
          <div class="prop-top">
            <span class="tipo" :class="m.tipo">{{ m.tipo === 'gasto' ? '− Gasto' : '+ Ingreso' }}</span>
            <input
              v-model.number="m.monto"
              class="input monto"
              type="number"
              inputmode="decimal"
              min="0"
              step="100"
              placeholder="Monto"
            />
          </div>
          <select v-model="m.categoria_id" class="input">
            <option :value="null" disabled>Categoría…</option>
            <option v-for="c in propuesta.opciones.categorias" :key="c.id" :value="c.id">
              {{ c.nombre }}
            </option>
          </select>
          <div class="prop-meta">
            <span>{{ m.descripcion }}</span>
            <span v-if="m.metodo">· {{ m.metodo }}</span>
            <span>· {{ m.fecha }}</span>
          </div>
          <p v-if="m.requiere_confirmacion_monto" class="warn">
            <i class="bi bi-exclamation-triangle"></i>
            {{ m.falta_monto
              ? 'No dijiste el monto. Escríbelo a mano.'
              : 'Ese monto no estaba en tu texto: la IA lo dedujo. Confírmalo.' }}
          </p>

          <!--
            El usuario ya declaró este fijo en /plan y ahora captura algo que se le
            parece. La app NO decide: pregunta. Si ella eligiera sola se equivocaria
            en los dos sentidos (crear dos arriendos, o tomar el de siempre como
            si fuera otro) y el usuario perdería la confianza en el aviso.
          -->
          <div v-if="m.coincidencias?.length" class="coincide">
            <p class="coincide-preg">
              <i class="bi bi-arrow-repeat"></i>
              ¿Este es tu <strong>{{ m.coincidencias[0].nombre }}</strong> de siempre
              ({{ dinero(m.coincidencias[0].monto) }}, día {{ m.coincidencias[0].dia }})?
              <span class="sub">{{ m.coincidencias[0].motivo }}</span>
            </p>
            <div class="coincide-botones">
              <button :class="['chip', m.eleccion === m.coincidencias[0].id ? 'on' : '']"
                @click="m.eleccion = m.eleccion === m.coincidencias[0].id ? null : m.coincidencias[0].id">
                Sí, es el mismo
              </button>
              <button :class="['chip', m.eleccion === 'nuevo' ? 'on' : '']"
                @click="m.eleccion = m.eleccion === 'nuevo' ? null : 'nuevo'">
                No, es otro
              </button>
              <button v-if="m.eleccion" class="link" @click="m.eleccion = null">Quitar</button>
            </div>
            <p v-if="m.eleccion === 'nuevo'" class="sub">
              Se creará un fijo nuevo con este movimiento, aparte de los que ya tienes.
            </p>
          </div>
        </div>

        <div v-if="propuesta.avisos.length" class="avisos">
          <p v-for="(a, i) in propuesta.avisos" :key="i"><i class="bi bi-info-circle"></i> {{ a }}</p>
        </div>

        <p class="sub total">Total de gastos: {{ dinero(total) }}</p>

        <button class="btn-mint full" :disabled="cargando" @click="confirmar">
          <span v-if="cargando" class="spinner"></span>
          <template v-else><i class="bi bi-check-lg"></i>
            Guardar {{ propuesta.movimientos.length }}
            {{ propuesta.movimientos.length === 1 ? 'movimiento' : 'movimientos' }}</template>
        </button>
        <button class="btn-ghost full" @click="propuesta = null">Corregir la frase</button>
      </template>

      <p v-if="error" class="alert">{{ error }}</p>
    </div>
  </div>
</template>

<style scoped>
.pill-captura {
  position: fixed;
  right: 16px;
  bottom: calc(96px + env(safe-area-inset-bottom));
  z-index: 28;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  border: 0;
  border-radius: 999px;
  background: var(--navy);
  color: var(--mint);
  font: 700 14px var(--font);
  box-shadow: 0 8px 22px rgba(5, 11, 59, .3);
  cursor: pointer;
}
.pill-captura:active { transform: scale(.96); }

.cap-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  background: rgba(5, 11, 59, .55);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 12px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
}
.cap-sheet {
  width: 100%;
  max-width: 480px;
  max-height: 88vh;
  overflow-y: auto;
  background: var(--surface);
  border-radius: 20px;
  padding: 18px;
  box-shadow: var(--shadow);
}
.cap-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.x { background: none; border: 0; font-size: 18px; color: var(--ink-soft); cursor: pointer; }

.fila-input { display: flex; gap: 8px; margin: 10px 0; }
.fila-input .input { flex: 1; min-width: 0; }
.mic {
  width: 46px; border: 1px solid var(--line); background: var(--surface);
  border-radius: 14px; font-size: 18px; color: var(--navy); cursor: pointer;
}
.mic.on { background: var(--danger); border-color: var(--danger); color: #fff; }
.mic:disabled { opacity: .5; }
.grab { display: flex; align-items: center; gap: 7px; font-size: 13px; color: var(--danger); margin: 0 0 8px; }
.grab .punto { width: 9px; height: 9px; border-radius: 50%; background: var(--danger); animation: latido 1s infinite; }
@keyframes latido { 50% { opacity: .25; } }

.full { width: 100%; margin-top: 8px; }

.auto { display: flex; gap: 10px; align-items: flex-start; margin-top: 14px; font-size: 13px; }
.auto input { margin-top: 3px; }
.auto span { display: flex; flex-direction: column; }
.auto em { font-style: normal; color: var(--ink-soft); font-size: 12px; margin-top: 2px; }
.quota { margin-top: 10px; text-align: center; }

.prop { border: 1px solid var(--line); border-radius: 14px; padding: 12px; margin-top: 10px; }
.prop.dudoso { border-color: var(--warning); background: rgba(216, 154, 39, .06); }
.prop-top { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.tipo { font: 700 12px var(--font); padding: 4px 8px; border-radius: 8px; }
.tipo.gasto { background: var(--danger-soft); color: var(--danger); }
.tipo.ingreso { background: var(--mint-soft); color: var(--mint-dark); }
.monto { flex: 1; text-align: right; font-weight: 700; }
.prop-meta { margin-top: 7px; font-size: 12px; color: var(--ink-soft); }
.warn { margin: 8px 0 0; font-size: 12px; color: var(--warning); font-weight: 600; }
.avisos { margin-top: 10px; font-size: 12px; color: var(--ink-soft); }
.avisos p { margin: 4px 0; }
.total { text-align: right; margin-top: 12px; }
  .coincide { margin-top: 10px; padding: 10px 12px; border-radius: 12px; background: var(--mint-soft); }
  .coincide-preg { margin: 0; font-size: 13px; line-height: 1.45; }
  .coincide-preg i { color: var(--mint-dark); margin-right: 4px; }
  .coincide-preg .sub { display: block; margin: 4px 0 0; font-size: 11.5px; }
  .coincide-botones { display: flex; gap: 6px; align-items: center; margin-top: 8px; flex-wrap: wrap; }
  .coincide .chip { padding: 6px 12px; font-size: 12.5px; }
</style>