<template>
  <main class="page">
    <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap">
      <button :class="['chip', tab === 'p' ? 'on' : '']" @click="tab = 'p'">Presupuestos</button>
      <button :class="['chip', tab === 'm' ? 'on' : '']" @click="tab = 'm'">Metas</button>
      <span style="flex: 1 1 auto"></span>
      <button class="btn-new" @click="showForm = !showForm">+ {{ tab === 'p' ? 'Nuevo presupuesto' : 'Nueva meta' }}</button>
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
import { computed, onMounted, reactive, ref } from 'vue'
import NumeroInput from '../components/NumeroInput.vue'
import api from '../services/api'
import { numero } from '../utils/formato'
type Cat = { id: string; nombre: string; tipo: string }
const tab = ref<'p' | 'm'>('p')
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
  const [c, p, m] = await Promise.all([
    api.get('/categorias', { params: { solo_activas: false } }),
    api.get('/presupuestos', { params: { periodo: mes.value } }).catch(() => ({ data: [] })),
    api.get('/metas').catch(() => ({ data: [] }))
  ])
  cats.value = c.data
  presupuestos.value = p.data
  metas.value = m.data
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
.chip{border:1px solid var(--navy);background:var(--surface);color:var(--navy);border-radius:99px;padding:8px 14px;font-weight:700}
.chip.on{background:var(--navy);color:#fff}
.sub{font-size:13px;opacity:.65}
.link{background:none;border:0;color:var(--ink-soft)}
.btn-new{background:var(--mint);color:var(--navy);border:0;border-radius:12px;padding:10px 14px;font-weight:800;white-space:nowrap}
.goal-img{width:100%;height:150px;object-fit:cover;border-radius:14px;display:block}
.dropzone{margin-top:8px;border:1.5px dashed var(--navy-line);border-radius:14px;padding:14px;text-align:center;color:var(--ink-soft);font-size:13px;cursor:pointer}
.dropzone.over{border-color:var(--mint-dark);background:var(--mint-soft);color:var(--ink)}
</style>
