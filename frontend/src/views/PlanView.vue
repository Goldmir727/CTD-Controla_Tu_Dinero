<template>
  <main class="page">
    <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap">
      <button :class="['chip', tab === 'p' ? 'on' : '']" @click="tab = 'p'">Presupuestos</button>
      <button :class="['chip', tab === 'm' ? 'on' : '']" @click="tab = 'm'">Metas</button>
      <button :class="['chip', tab === 'f' ? 'on' : '']" @click="tab = 'f'">Fijos</button>
      <span style="flex: 1 1 auto"></span>
      <button class="btn-new" @click="showForm = !showForm; if (!showForm) cerrarFormFijo()">
        + {{ tab === 'p' ? 'Nuevo presupuesto' : tab === 'm' ? 'Nueva meta' : editando ? 'Guardar cambios' : 'Nuevo fijo' }}
      </button>
    </div>

    <section v-if="tab === 'p'" style="margin-top: 14px">
      <div style="display: flex; gap: 8px; align-items: center">
        <span class="eyebrow">PRESUPUESTO DE</span>
        <input v-model="mes" type="month" class="input" style="max-width: 160px" @change="cargar" />
      </div>

      <form v-if="showForm" @submit.prevent="crearPresupuesto" class="card" style="margin-top: 10px; display: grid; gap: 8px">
        <select v-model="np.categoria_id" class="input" required>
          <option value="" disabled>Categoría de gasto</option>
          <option v-for="c in catsGastoDisponibles" :key="c.id" :value="c.id">{{ c.nombre }}</option>
        </select>
        <NumeroInput v-model="np.monto" placeholder="Monto límite (ej: 500.000)" required />
        <button class="btn-primary">Guardar presupuesto</button>
      </form>

      <div v-if="!presupuestos.length" class="card" style="margin-top: 10px">
        <p class="sub">Sin presupuestos en {{ mes }}. Crea uno para controlar una categoría.</p>
      </div>
      <div v-for="b in presupuestos" :key="b.id" class="card" style="margin-top: 10px">
        <div style="display: flex; justify-content: space-between"><strong>{{ b.categoria }}</strong><button class="link" @click="eliminarPresupuesto(b.id)">Eliminar</button></div>
        <div>${{ fmt(b.gastado) }} / ${{ fmt(b.monto) }}</div>
        <div :class="['progress', b.estado === 'excedido' ? 'bad' : b.estado === 'alerta' ? 'warn' : '']" style="margin: 8px 0"><span :style="{ width: Math.min(b.porcentaje_uso, 100) + '%' }"></span></div>
        <div v-if="b.estado !== 'excedido'">${{ fmt(b.restante) }} restantes · Vas dentro de tu límite.</div>
        <div v-else class="alert">Superaste el presupuesto en ${{ fmt(-b.restante) }}</div>
      </div>
    </section>

    <section v-else-if="tab === 'f'" style="margin-top: 14px">
      <section v-if="resumenFijos && resumenFijos.cantidad" class="card" style="margin-bottom: 12px">
        <div class="eyebrow">FIJOS DEL MES</div>
        <div class="grid-2" style="margin-top: 6px">
          <div>
            <div class="sub">Entran</div>
            <strong style="color: var(--mint-dark)">${{ fmt(resumenFijos.ingresos_fijos_mes) }}</strong>
          </div>
          <div>
            <div class="sub">Salen</div>
            <strong style="color: var(--danger)">${{ fmt(resumenFijos.gastos_fijos_mes) }}</strong>
          </div>
        </div>
        <div v-if="resumenFijos.ratio_fijo != null" class="sub" style="margin-top: 8px">
          El {{ resumenFijos.ratio_fijo }}% de lo que gastas es fijo. Si sube, tu margen
          desaparece aunque el saldo final se vea bien.
        </div>
      </section>

      <form v-if="showForm" @submit.prevent="guardarFijo" class="card" style="display: grid; gap: 8px">
        <div style="display: flex; gap: 8px">
          <button type="button" :class="['chip', nf.tipo === 'gasto' ? 'on' : '']" @click="nf.tipo = 'gasto'">Sale</button>
          <button type="button" :class="['chip', nf.tipo === 'ingreso' ? 'on' : '']" @click="nf.tipo = 'ingreso'">Entra</button>
        </div>
        <input v-model="nf.nombre" :placeholder="nf.tipo === 'gasto' ? 'Ej. Arriendo' : 'Ej. Salario'" class="input" required />
        <NumeroInput v-model="nf.monto" placeholder="Monto (ej: 1.200.000)" required />
        <div style="display: flex; gap: 8px">
          <select v-model="nf.frecuencia" class="input">
            <option value="mensual">Cada mes</option>
            <option value="quincenal">Cada 15 días</option>
            <option value="semanal">Cada semana</option>
          </select>
          <input v-model.number="nf.dia" type="number" min="1" max="31" class="input" style="max-width: 110px" title="Día del mes en que se cobra o se paga" />
        </div>
        <p class="sub" style="margin: 0">
          {{ nf.frecuencia === 'mensual' ? 'Se cobra o paga el día' : 'Primer día en que cae' }}
          {{ nf.dia || '—' }}{{ nf.frecuencia === 'semanal' ? ' y luego cada 7 días' : nf.frecuencia === 'quincenal' ? ' y luego 15 días después' : '' }}.
        </p>
        <select v-model="nf.categoria_id" class="input">
          <option value="">Sin categoría</option>
          <option v-for="c in catsPara(nf.tipo)" :key="c.id" :value="c.id">{{ c.nombre }}</option>
        </select>
        <select v-model="nf.cuenta_id" class="input">
          <option value="">Sin cuenta</option>
          <option v-for="c in cuentas" :key="c.id" :value="c.id">{{ c.nombre }}</option>
        </select>
        <button class="btn-primary">Guardar fijo</button>
      </form>

      <div v-if="!fijos.length" class="card" style="margin-top: 10px">
        <p class="sub">
          Sin gastos fijos todavía. Sirven para que el motor separe lo que siempre pagas de lo
          variable y no te diga "te alcanza" cuando en realidad no.
        </p>
      </div>

      <div v-for="f in fijos" :key="f.id" class="card" style="margin-top: 10px" :style="f.activo ? '' : 'opacity:.55'">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px">
          <div style="min-width: 0">
            <strong>{{ f.nombre }}</strong>
            <div class="sub">
              {{ cuando(f) }}<span v-if="f.categoria"> · {{ f.categoria }}</span>
              <span v-if="f.frecuencia !== 'mensual'"> · equivale a ${{ fmt(f.monto_mes) }}/mes</span>
            </div>
          </div>
          <strong :style="f.tipo === 'ingreso' ? 'color:var(--mint-dark)' : 'color:var(--danger)'">
            {{ f.tipo === 'ingreso' ? '+' : '−' }}${{ fmt(f.monto) }}
          </strong>
        </div>
        <div style="display: flex; gap: 10px; margin-top: 10px; align-items: center">
          <button class="link" @click="editarFijo(f)">Editar</button>
          <button class="link" @click="toggleFijo(f)">{{ f.activo ? 'Pausar' : 'Activar' }}</button>
          <button class="link" @click="eliminarFijo(f.id)">Eliminar</button>
        </div>
      </div>
    </section>

    <section v-else style="margin-top: 14px">
      <form v-if="showForm" @submit.prevent="crearMeta" class="card" style="display: grid; gap: 8px">
        <input v-model="nm.nombre" placeholder="Ej. Computador" class="input" required />
        <NumeroInput v-model="nm.objetivo" placeholder="Monto objetivo (ej: 4.000.000)" required />
        <input v-model="nm.fecha_objetivo" type="date" class="input" />
        <button class="btn-primary">Guardar meta</button>
      </form>

      <div v-if="!metas.length" class="card" style="margin-top: 10px">
        <p class="sub">Sin metas. Crea una para ver cuánto te falta y cuánto ahorrar por mes.</p>
      </div>
      <div v-for="m in metas" :key="m.id" :class="['card', m.faltante <= 0 ? 'card-glow' : '']" style="margin-top: 10px">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px">
          <span style="min-width: 0; overflow-wrap: anywhere"><span v-if="m.faltante <= 0" class="done-flag">✓ META COMPLETADA · </span><strong>{{ m.nombre }}</strong></span>
          <button class="link" style="flex: none" @click="eliminarMeta(m.id)">Eliminar</button>
        </div>
        <div v-if="m.imagen_url" style="position: relative; margin-top: 8px">
          <img :src="m.imagen_url" :alt="m.nombre" class="goal-img" />
          <button class="btn-ghost" style="position: absolute; top: 6px; right: 6px; background: rgba(255,255,255,.9)" @click="quitarImagen(m)">Quitar</button>
        </div>
        <div v-else class="dropzone" :class="{ over: dragOver === m.id }"
          @dragover.prevent="dragOver = m.id" @dragleave="dragOver = ''"
          @drop.prevent="soltarImagen($event, m)" @click="elegirImagen(m)">
          <i class="bi bi-image"></i> Arrastra una imagen aquí o toca para elegir
        </div>
        <input :ref="(el) => (fileInputs[m.id] = el as HTMLInputElement)" type="file" accept="image/png,image/jpeg,image/webp" hidden
          @change="archivoElegido($event, m)" />
        <div>${{ fmt(m.ahorrado) }} / ${{ fmt(m.objetivo) }} · {{ Math.round(m.porcentaje) }}%</div>
        <div class="progress" style="margin: 8px 0"><span :style="{ width: Math.min(m.porcentaje, 100) + '%' }"></span></div>
        <div v-if="m.faltante > 0">Faltan ${{ fmt(m.faltante) }}<span v-if="m.ahorro_requerido_mensual != null"> · Necesitas ${{ fmt(m.ahorro_requerido_mensual) }} / mes</span><span v-else> · Sin fecha: aporta a tu ritmo</span></div>
        <div v-else>¡Meta cumplida! Excedente ${{ fmt(m.excedente ?? 0) }}</div>
        <form @submit.prevent="aportar(m)" style="display: flex; gap: 8px; margin-top: 8px">
          <NumeroInput v-model="m._aporte" placeholder="Aportar $" style="flex: 1; min-width: 0" />
          <button class="btn-new" style="flex: none">Aportar</button>
        </form>
        <p class="sub">Seguimiento: no aparta dinero real de tus cuentas.</p>
      </div>
    </section>
    <p v-if="error" class="alert">{{ error }}</p>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import NumeroInput from '../components/NumeroInput.vue'
import api from '../services/api'
import { numero } from '../utils/formato'
type Cat = { id: string; nombre: string; tipo: string }
const tab = ref<'p' | 'm' | 'f'>('p')
const mes = ref(new Date().toISOString().slice(0, 7))
const showForm = ref(false)
const error = ref('')
const cats = ref<Cat[]>([])
const presupuestos = ref<{ id: string; categoria: string; categoria_id: string; monto: number; gastado: number; restante: number; porcentaje_uso: number; estado: string }[]>([])
const metas = ref<{ id: string; nombre: string; objetivo: number; ahorrado: number; faltante: number; porcentaje: number; excedente?: number; ahorro_requerido_mensual: number | null; imagen_url?: string | null; _aporte?: number | null }[]>([])
const dragOver = ref('')
const fileInputs = reactive<Record<string, HTMLInputElement | null>>({})
const np = reactive({ categoria_id: '', monto: null as number | null })
const nm = reactive({ nombre: '', objetivo: null as number | null, fecha_objetivo: '' })
const fmt = (n: number) => numero(n)
const usados = computed(() => new Set(presupuestos.value.map((b) => b.categoria_id)))
const catsGastoDisponibles = computed(() => cats.value.filter((c) => (c.tipo === 'gasto' || c.tipo === 'ambos') && !usados.value.has(c.id)))

async function cargar() {
  error.value = ''
  const [c, p, m, r, cu] = await Promise.all([
    api.get('/categorias', { params: { solo_activas: false } }),
    api.get('/presupuestos', { params: { periodo: mes.value } }).catch(() => ({ data: [] })),
    api.get('/metas').catch(() => ({ data: [] })),
    api.get('/recurrentes').catch(() => ({ data: { items: [], resumen: null } })),
    api.get('/cuentas').catch(() => ({ data: [] }))
  ])
  cats.value = c.data
  presupuestos.value = p.data
  metas.value = m.data
  fijos.value = r.data.items ?? []
  resumenFijos.value = r.data.resumen ?? null
  cuentas.value = cu.data
}
async function crearPresupuesto() {
  try { await api.post('/presupuestos', { categoria_id: np.categoria_id, monto: np.monto, periodo: mes.value }); showForm.value = false; np.categoria_id = ''; np.monto = null; await cargar() }
  catch { error.value = 'No se pudo crear (¿ya existe para esa categoría y mes?).' }
}
async function eliminarPresupuesto(id: string) { await api.delete(`/presupuestos/${id}`); await cargar() }
async function crearMeta() {
  try {
    await api.post('/metas', { nombre: nm.nombre, objetivo: nm.objetivo, fecha_objetivo: nm.fecha_objetivo || null })
    showForm.value = false; nm.nombre = ''; nm.objetivo = null; nm.fecha_objetivo = ''; await cargar()
  } catch { error.value = 'No se pudo crear la meta.' }
}
async function aportar(m: { id: string; _aporte?: number | null }) {
  if (!m._aporte || m._aporte <= 0) return
  await api.post(`/metas/${m.id}/aportes`, { monto: m._aporte }, { headers: { 'Idempotency-Key': crypto.randomUUID() } })
  m._aporte = null; await cargar()
}
async function eliminarMeta(id: string) {
  if (!confirm('¿Eliminar meta y sus aportes?')) return
  await api.delete(`/metas/${id}`, { params: { confirm: true } }); await cargar()
}

// ---- Gastos e ingresos fijos ----
// El backend ya tenia todo esto; faltaba la pantalla. Sin ella, un fijo solo
// aparecia si la captura lo proponia, y el usuario no tenia forma de corregir
// uno mal detectado ni de agregar uno que el modelo nunca iba a proponer.

type Fijo = {
  id: string; nombre: string; tipo: 'ingreso' | 'gasto'; monto: number; monto_mes: number
  dia: number; frecuencia: string; activo: boolean; cuenta_id?: string | null
  categoria_id?: string | null; categoria?: string | null
}
type ResumenFijos = {
  cantidad: number; ingresos_fijos_mes: number; gastos_fijos_mes: number
  neto_fijo_mes: number; ratio_fijo: number | null
}
const fijos = ref<Fijo[]>([])
const resumenFijos = ref<ResumenFijos | null>(null)
const cuentas = ref<{ id: string; nombre: string }[]>([])
const editando = ref<string | null>(null)
const nf = reactive({
  nombre: '', tipo: 'gasto' as 'gasto' | 'ingreso', monto: null as number | null,
  dia: 1, frecuencia: 'mensual', categoria_id: '', cuenta_id: ''
})

function catsPara(tipo: string) {
  return cats.value.filter((c) => c.tipo === tipo || c.tipo === 'ambos')
}

// "el día 20", "quincenal", etc. Sin esto el usuario tiene que traducir la
// frecuencia a un calendario mental, que es justo lo que la app hace por él.
function cuando(f: Fijo) {
  const dia = f.dia
  if (f.frecuencia === 'semanal') return `cada semana desde el ${dia}`
  if (f.frecuencia === 'quincenal') return `quincenal desde el ${dia}`
  return `el día ${dia} de cada mes`
}

async function guardarFijo() {
  error.value = ''
  const cuerpo = {
    nombre: nf.nombre.trim(), tipo: nf.tipo, monto: nf.monto,
    dia: Math.max(1, Math.min(31, nf.dia || 1)), frecuencia: nf.frecuencia,
    categoria_id: nf.categoria_id || null, cuenta_id: nf.cuenta_id || null
  }
  try {
    if (editando.value) await api.patch(`/recurrentes/${editando.value}`, cuerpo)
    else await api.post('/recurrentes', cuerpo)
    cerrarFormFijo()
    await cargar()
  } catch (e: any) {
    // El backend responde cosas utiles ("La categoría 'Comida' no aplica a
    // ingresos"); se muestran tal cual en vez de un "no se pudo" genérico.
    error.value = e?.response?.data?.detail ?? 'No se pudo guardar el fijo.'
  }
}
function editarFijo(f: Fijo) {
  editando.value = f.id
  Object.assign(nf, {
    nombre: f.nombre, tipo: f.tipo, monto: f.monto, dia: f.dia,
    frecuencia: f.frecuencia, categoria_id: f.categoria_id ?? '', cuenta_id: f.cuenta_id ?? ''
  })
  showForm.value = true
}
function cerrarFormFijo() {
  showForm.value = false; editando.value = null
  Object.assign(nf, {
    nombre: '', tipo: 'gasto', monto: null, dia: 1, frecuencia: 'mensual',
    categoria_id: '', cuenta_id: ''
  })
}
async function toggleFijo(f: Fijo) {
  await api.patch(`/recurrentes/${f.id}/toggle`); await cargar()
}
async function eliminarFijo(id: string) {
  if (!confirm('¿Eliminar este fijo?')) return
  await api.delete(`/recurrentes/${id}`); await cargar()
}
watch(tab, (t) => { if (t !== 'f') cerrarFormFijo() })
// Imagen de meta: arrastrar+soltar (PC) o tocar para elegir. Se reduce a máx 800px JPEG.
function archivoDe(e: DragEvent | Event): File | null {
  if ('dataTransfer' in e && e.dataTransfer) {
    const f = [...(e.dataTransfer.files || [])].find((x) => x.type.startsWith('image/'))
    return f ?? null
  }
  const inp = e.target as HTMLInputElement
  return inp.files?.[0] ?? null
}
function aDataURL(f: File): Promise<string> {
  return new Promise((res, rej) => {
    const url = URL.createObjectURL(f)
    const img = new Image()
    img.onload = () => {
      const s = Math.min(1, 800 / img.width)
      const c = document.createElement('canvas')
      c.width = Math.round(img.width * s); c.height = Math.round(img.height * s)
      c.getContext('2d')!.drawImage(img, 0, 0, c.width, c.height)
      URL.revokeObjectURL(url)
      res(c.toDataURL('image/jpeg', 0.82))
    }
    img.onerror = rej
    img.src = url
  })
}
async function subirImagen(m: { id: string }, f: File | null) {
  if (!f) return
  error.value = ''
  try {
    const dataUrl = await aDataURL(f)
    if (dataUrl.length > 700_000) { error.value = 'Imagen muy pesada aun comprimida.'; return }
    await api.patch(`/metas/${m.id}`, { imagen_url: dataUrl })
    await cargar()
  } catch { error.value = 'No se pudo subir la imagen (JPG/PNG/WebP).' }
}
function soltarImagen(e: DragEvent, m: { id: string }) { dragOver.value = ''; void subirImagen(m, archivoDe(e)) }
function elegirImagen(m: { id: string }) { fileInputs[m.id]?.click() }
function archivoElegido(e: Event, m: { id: string }) {
  void subirImagen(m, archivoDe(e))
  if (fileInputs[m.id]) fileInputs[m.id]!.value = ''
}
async function quitarImagen(m: { id: string }) { await api.patch(`/metas/${m.id}`, { imagen_url: null }); await cargar() }
onMounted(cargar)
</script>

<style>
/* .chip vive en tokens.css */
.sub{font-size:13px;opacity:.65}
.link{background:none;border:0;color:var(--ink-soft)}
.btn-new{background:var(--mint);color:var(--navy);border:0;border-radius:12px;padding:10px 14px;font-weight:800;white-space:nowrap}
.goal-img{width:100%;height:150px;object-fit:cover;border-radius:14px;display:block}
.dropzone{margin-top:8px;border:1.5px dashed var(--navy-line);border-radius:14px;padding:14px;text-align:center;color:var(--ink-soft);font-size:13px;cursor:pointer}
.dropzone.over{border-color:var(--mint-dark);background:var(--mint-soft);color:var(--ink)}
</style>
