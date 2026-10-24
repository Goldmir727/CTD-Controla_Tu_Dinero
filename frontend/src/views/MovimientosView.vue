<template>
  <main class="page rise">
    <div style="display: flex; justify-content: space-between; align-items: center">
      <h2 style="margin: 0">Movimientos</h2>
    </div>
    <p class="eyebrow">{{ mes }} <span class="unidad">cifras en {{ cod }}</span></p>
    <!-- Fijos vive aqui desde Plan: es plata que entra o sale mas de una vez,
         y el usuario la busca donde ve el historial, no en planificacion. -->
    <div style="display: flex; gap: 8px; margin: 10px 0 0">
      <button :class="['chip', seccion === 'movs' ? 'on' : '']" @click="irASec('movs')">Registros</button>
      <button :class="['chip', seccion === 'fijos' ? 'on' : '']" @click="irASec('fijos')">Fijos</button>
    </div>
    <template v-if="seccion === 'movs'">
    <div style="display: flex; gap: 8px; margin: 10px 0">
      <button v-for="f in ['todos', 'ingreso', 'gasto']" :key="f" :class="['chip', filtro === f ? 'on' : '']" @click="filtro = f">{{ label(f) }}</button>
    </div>
    <div class="search-wrap"><i class="bi bi-search"></i><input v-model="q" placeholder="Buscar movimientos..." aria-label="Buscar movimientos" class="input" /></div>
    <button class="link" aria-haspopup="dialog" @click="sheet = true">Filtros: {{ cuentaNombre }} · {{ categoriaNombre }} · {{ orden }}</button>
    <div v-if="loading" style="display: grid; gap: 8px; margin-top: 14px">
      <div class="skel" style="height: 58px" v-for="i in [1, 2, 3]" :key="i"></div>
    </div>
    <div v-if="!loading && !items.length" class="empty">
      <strong>Sin movimientos aquí</strong>
      Registra tu primer {{ filtro === 'todos' ? 'movimiento' : filtro }} con el botón +.
    </div>
    <div v-for="g in grupos" :key="g.titulo" style="margin-top: 14px">
      <div class="eyebrow">{{ g.titulo }}</div>
      <button v-for="m in g.items" :key="m.id" class="row" style="width: 100%; text-align: left; background: none; border: 0; border-bottom: 1px solid var(--line); font: inherit; color: inherit; cursor: pointer" @click="abrirEdicion(m)">
        <span :class="['icon-badge', m.tipo === 'ingreso' ? 'is-in' : 'is-out']"><i :class="['bi', m.tipo === 'ingreso' ? 'bi-arrow-up' : 'bi-arrow-down']"></i></span>
        <div style="flex: 1"><div>{{ m.descripcion || 'Movimiento' }}</div><div class="sub">{{ m.categoria }} · {{ m.cuenta }}</div></div>
        <strong :class="['amount', m.tipo === 'ingreso' ? 't-pos' : 't-neg']">{{ m.tipo === 'ingreso' ? '+' : '−' }}${{ fmt(m.monto) }}</strong>
      </button>
    </div>
    <div v-if="sheet" class="sheet-back" @click="sheet = false">
      <div ref="filtroSheet" class="sheet" role="dialog" aria-modal="true" aria-labelledby="filtro-titulo" @click.stop>
        <div class="sheet-head">
          <h3 id="filtro-titulo">Filtros</h3>
          <button class="x-sheet" aria-label="Cerrar filtros" @click="sheet = false"><i class="bi bi-x-lg"></i></button>
        </div>
        <div class="field">
          <label for="f-cuenta">Cuenta</label>
          <select id="f-cuenta" v-model="cuentaId" class="input"><option value="">Todas las cuentas</option><option v-for="c in cuentas" :key="c.id" :value="c.id">{{ c.nombre }}</option></select>
        </div>
        <div class="field">
          <label for="f-categoria">Categoría</label>
          <select id="f-categoria" v-model="categoriaId" class="input"><option value="">Todas las categorías</option><option v-for="c in categorias" :key="c.id" :value="c.id">{{ c.nombre }}</option></select>
        </div>
        <div class="field">
          <label for="f-orden">Orden</label>
          <select id="f-orden" v-model="orden" class="input"><option value="recientes">Más recientes</option><option value="monto">Mayor monto</option></select>
        </div>
        <button class="btn-primary" @click="sheet = false">Aplicar</button>
      </div>
    </div>
  <div v-if="editando" class="sheet-back" @click="cerrarEdicion">
      <div ref="editSheet" class="sheet" role="dialog" aria-modal="true" aria-labelledby="ed-titulo" @click.stop>
        <div class="sheet-head">
          <h3 id="ed-titulo">Editar movimiento</h3>
          <button class="x-sheet" aria-label="Cerrar edición" @click="cerrarEdicion"><i class="bi bi-x-lg"></i></button>
        </div>
        <p class="sub" style="margin: -4px 0 2px">
          Corregir un clic mal dado aquí es mejor que borrarlo y volver a escribirlo.
        </p>
        <div class="field">
          <label for="ed-desc">Descripción</label>
          <input id="ed-desc" v-model="ed.descripcion" placeholder="Ej. Almuerzo" class="input" data-autofocus />
        </div>
        <div class="field">
          <label for="ed-monto">Monto</label>
          <NumeroInput id="ed-monto" v-model="ed.monto" placeholder="Monto" />
        </div>
        <div class="field">
          <label for="ed-fecha">Fecha</label>
          <input id="ed-fecha" v-model="ed.fecha" type="date" class="input" />
        </div>
        <div class="field">
          <span class="etiqueta">Tipo</span>
          <div role="group" aria-label="Tipo de movimiento" style="display: flex; gap: 8px">
            <button type="button" :class="['chip', ed.tipo === 'gasto' ? 'on' : '']" :aria-pressed="ed.tipo === 'gasto'" @click="ed.tipo = 'gasto'">Gasto</button>
            <button type="button" :class="['chip', ed.tipo === 'ingreso' ? 'on' : '']" :aria-pressed="ed.tipo === 'ingreso'" @click="ed.tipo = 'ingreso'">Ingreso</button>
          </div>
        </div>
        <div class="field">
          <label for="ed-categoria">Categoría</label>
          <select id="ed-categoria" v-model="ed.categoria_id" class="input">
            <option value="">Sin categoría</option>
            <option v-for="c in catsPara(ed.tipo)" :key="c.id" :value="c.id">{{ c.nombre }}</option>
          </select>
        </div>
        <div class="field">
          <label for="ed-cuenta">Cuenta</label>
          <select id="ed-cuenta" v-model="ed.cuenta_id" class="input">
            <option value="">Sin cuenta</option>
            <option v-for="c in cuentas" :key="c.id" :value="c.id">{{ c.nombre }}</option>
          </select>
        </div>
        <div class="field">
          <label for="ed-metodo">Método de pago</label>
          <select id="ed-metodo" v-model="ed.metodo_id" class="input">
            <option value="">Sin método</option>
            <option v-for="m in metodos" :key="m.id" :value="m.id">{{ m.nombre }}</option>
          </select>
        </div>
        <p v-if="edError" class="alert" role="alert" aria-live="assertive">{{ edError }}</p>
        <button class="btn-primary" :disabled="guardando" @click="guardarEdicion">
          {{ guardando ? 'Guardando…' : 'Guardar cambios' }}
        </button>
        <button class="link" style="color: var(--danger-text); margin-top: 0" @click="borrarEditando">Eliminar movimiento</button>
      </div>
    </div>
    </template>

    <SeccionFijos v-else-if="seccion === 'fijos'" />
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NumeroInput from '../components/NumeroInput.vue'
import SeccionFijos from '../components/SeccionFijos.vue'
import api from '../services/api'
import { useDialog } from '../composables/useDialog'
import { confirmar } from '../composables/useConfirm'
import { useToast } from '../composables/useToast'
import { codigo, numero } from '../utils/formato'
type Mov = { id: string; tipo: string; monto: number; fecha: string; descripcion: string; categoria_id?: string; cuenta_id?: string; metodo_id?: string | null; categoria?: string; cuenta?: string }
const route = useRoute(); const router = useRouter()
// "Movimientos?tab=fijos" abre directo en la pestaña de fijos (atajo desde Inicio).
const seccion = ref(route.query.tab === 'fijos' ? 'fijos' : 'movs')
function irASec(s: 'movs' | 'fijos') {
  seccion.value = s
  router.replace({ query: s === 'fijos' ? { tab: 'fijos' } : {} })
}
const filtro = ref('todos'); const q = ref(''); const mes = ref(new Date().toISOString().slice(0, 7))
const items = ref<Mov[]>([])
// La moneda es la del usuario, no una suposicion: si esta en USD, el selector
// de cuenta y metodo ya muestran simbolos distintos y el codigo debe acorde.
const moneda = ref('COP')
const cod = computed(() => codigo(moneda.value)); const cuentas = ref<{ id: string; nombre: string }[]>([]); const categorias = ref<{ id: string; nombre: string; tipo: string }[]>([])
const metodos = ref<{ id: string; nombre: string }[]>([])
const sheet = ref(false); const filtroSheet = ref<HTMLElement | null>(null)
const cuentaId = ref(''); const categoriaId = ref(''); const orden = ref('recientes')
const loading = ref(true)
const toast = useToast()

useDialog(sheet, filtroSheet, () => { sheet.value = false })
const label = (f: string) => f === 'todos' ? 'Todos' : f === 'ingreso' ? 'Ingresos' : 'Gastos'
const fmt = (n: number) => numero(n)
const cuentaNombre = computed(() => cuentas.value.find((c) => c.id === cuentaId.value)?.nombre ?? 'todas')
const categoriaNombre = computed(() => categorias.value.find((c) => c.id === categoriaId.value)?.nombre ?? 'todas')

// ---- Editar un movimiento ----
// El caso real: "gasté 200 en un dulce" queda como $200 pero era un desayuno
// de $8.000, o al reves. Antes habia que borrar y volver a capturar, y con la
// captura rapida el usuario lo hacia mal de nuevo la mitad de las veces.
const editando = ref<Mov | null>(null)
const editSheet = ref<HTMLElement | null>(null)
const guardando = ref(false)
const edError = ref('')

useDialog(computed(() => editando.value !== null), editSheet, cerrarEdicion)
const ed = reactive({ tipo: 'gasto' as 'gasto' | 'ingreso', monto: null as number | null,
                      fecha: '', descripcion: '', categoria_id: '', cuenta_id: '', metodo_id: '' })

function catsPara(tipo: string) {
  return categorias.value.filter((c) => c.tipo === tipo || c.tipo === 'ambos')
}
function abrirEdicion(m: Mov) {
  editando.value = m; edError.value = ''
  Object.assign(ed, {
    tipo: m.tipo === 'ingreso' ? 'ingreso' : 'gasto', monto: m.monto, fecha: m.fecha,
    descripcion: m.descripcion ?? '', categoria_id: m.categoria_id ?? '',
    cuenta_id: m.cuenta_id ?? '', metodo_id: m.metodo_id ?? ''
  })
}
function cerrarEdicion() { editando.value = null; edError.value = '' }
async function guardarEdicion() {
  if (!editando.value) return
  edError.value = ''
  if (!ed.monto || ed.monto <= 0) { edError.value = 'El monto debe ser mayor que cero.'; return }
  if (!ed.cuenta_id) { edError.value = 'Elige una cuenta: el saldo de todas depende de esto.'; return }
  guardando.value = true
  try {
    await api.patch(`/movimientos/${editando.value.id}`, {
      tipo: ed.tipo, monto: ed.monto, fecha: ed.fecha, descripcion: ed.descripcion,
      categoria_id: ed.categoria_id || null, cuenta_id: ed.cuenta_id,
      metodo_id: ed.metodo_id || null
    })
    cerrarEdicion(); await cargar()
  } catch (e: any) {
    edError.value = e?.response?.data?.detail ?? 'No se pudo guardar.'
  } finally { guardando.value = false }
}
async function borrarEditando() {
  if (!editando.value) return
  if (!(await confirmar({ titulo: '¿Eliminar este movimiento?', mensaje: 'Se quita de la cuenta y del historial. No se puede deshacer.', ok: 'Eliminar', peligro: true }))) return
  await api.delete(`/movimientos/${editando.value.id}`); toast.mostrar('Movimiento eliminado')
  cerrarEdicion(); await cargar()
}
async function cargar() {
  loading.value = true
  try {
    const { data } = await api.get('/movimientos', { params: { tipo: filtro.value === 'todos' ? undefined : filtro.value, q: q.value || undefined, cuenta_id: cuentaId.value || undefined, categoria_id: categoriaId.value || undefined, page_size: 100 } })
    let list: Mov[] = data.items
    const catMap = Object.fromEntries(categorias.value.map((c) => [c.id, c.nombre]))
    const cueMap = Object.fromEntries(cuentas.value.map((c) => [c.id, c.nombre]))
    list = list.map((m) => ({ ...m, categoria: catMap[m.categoria_id ?? ''] ?? '', cuenta: cueMap[m.cuenta_id ?? ''] ?? '' }))
    if (orden.value === 'monto') list = [...list].sort((a, b) => b.monto - a.monto)
    items.value = list
  } finally { loading.value = false }
}
const grupos = computed(() => {
  const hoy = new Date().toISOString().slice(0, 10)
  const map = new Map<string, Mov[]>()
  for (const m of items.value) {
    const k = m.fecha === hoy ? 'HOY' : m.fecha
    if (!map.has(k)) map.set(k, [])
    map.get(k)!.push(m)
  }
  return [...map.entries()].map(([titulo, items]) => ({ titulo, items }))
})
onMounted(async () => {
  const [cu, ca, me] = await Promise.all([
    api.get('/cuentas'),
    api.get('/categorias', { params: { solo_activas: false } }),
    api.get('/metodos-pago').catch(() => ({ data: [] }))
  ])
  cuentas.value = cu.data; categorias.value = ca.data; metodos.value = me.data
  api.get('/auth/me').then(({ data }) => { moneda.value = data.moneda ?? 'COP' }).catch(() => {})
  await cargar()
})
watch([filtro, cuentaId, categoriaId, orden], cargar)
let t: ReturnType<typeof setTimeout>
watch(q, () => { clearTimeout(t); t = setTimeout(cargar, 350) })
</script>

<style>
/* .chip vive en tokens.css */
.link { background: none; border: 0; color: var(--ink-soft); margin-top: 8px; }
.unidad { color: var(--ink-soft); font-weight: 600; }
.row { display: flex; align-items: center; gap: 12px; min-height: 56px; padding: 12px 2px; border-bottom: 1px solid var(--line); }
.btn-new { background: var(--mint); color: var(--navy); border: 0; border-radius: 12px; padding: 10px 14px; font-weight: 800; }
.sheet-back { position: fixed; inset: 0; background: rgba(5,11,59,.45); z-index: var(--z-sheet); display: flex; align-items: flex-end; justify-content: center; }
.sheet {
  background: var(--surface); color: var(--ink);
  width: 100%; max-width: 480px; max-height: 92dvh; overflow-y: auto;
  border-radius: 20px 20px 0 0;
  padding: 18px 18px calc(18px + var(--safe-bottom));
  display: grid; gap: 10px;
}
.sheet-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.sheet-head h3 { margin: 0; }
.x-sheet {
  width: 44px; height: 44px; display: inline-flex; align-items: center; justify-content: center;
  background: none; border: 0; border-radius: 12px; color: var(--ink-soft); cursor: pointer;
}
.x-sheet:focus-visible { outline: none; box-shadow: 0 0 0 3px rgba(0, 255, 171, 0.25); }
.etiqueta { font-size: 13px; font-weight: 700; color: var(--ink-soft); }
</style>
