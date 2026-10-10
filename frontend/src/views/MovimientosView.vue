<template>
  <main class="page rise">
    <div style="display: flex; justify-content: space-between; align-items: center">
      <h2 style="margin: 0">Movimientos</h2>
    </div>
    <p class="eyebrow">{{ mes }}</p>
    <div style="display: flex; gap: 8px; margin: 10px 0">
      <button v-for="f in ['todos', 'ingreso', 'gasto']" :key="f" :class="['chip', filtro === f ? 'on' : '']" @click="filtro = f">{{ label(f) }}</button>
    </div>
    <div class="search-wrap"><i class="bi bi-search"></i><input v-model="q" placeholder="Buscar movimientos..." class="input" /></div>
    <button class="link" @click="sheet = true">Filtros: {{ cuentaNombre }} · {{ categoriaNombre }} · {{ orden }}</button>
    <div v-if="loading" style="display: grid; gap: 8px; margin-top: 14px">
      <div class="skel" style="height: 58px" v-for="i in [1, 2, 3]" :key="i"></div>
    </div>
    <div v-if="!loading && !items.length" class="empty">
      <strong>Sin movimientos aquí</strong>
      Registra tu primer {{ filtro === 'todos' ? 'movimiento' : filtro }} con el botón +.
    </div>
    <div v-for="g in grupos" :key="g.titulo" style="margin-top: 14px">
      <div class="eyebrow">{{ g.titulo }}</div>
      <div v-for="m in g.items" :key="m.id" class="row">
        <span :class="['icon-badge', m.tipo === 'ingreso' ? 'is-in' : 'is-out']"><i :class="['bi', m.tipo === 'ingreso' ? 'bi-arrow-up' : 'bi-arrow-down']"></i></span>
        <div style="flex: 1"><div>{{ m.descripcion || 'Movimiento' }}</div><div class="sub">{{ m.categoria }} · {{ m.cuenta }}</div></div>
        <strong :class="['amount', m.tipo === 'ingreso' ? 't-pos' : 't-neg']">{{ m.tipo === 'ingreso' ? '+' : '−' }}${{ fmt(m.monto) }}</strong>
      </div>
    </div>
    <div v-if="sheet" class="sheet-back" @click="sheet = false">
      <div class="sheet" @click.stop>
        <h3>Filtros</h3>
        <select v-model="cuentaId" class="input"><option value="">Todas las cuentas</option><option v-for="c in cuentas" :key="c.id" :value="c.id">{{ c.nombre }}</option></select>
        <select v-model="categoriaId" class="input"><option value="">Todas las categorías</option><option v-for="c in categorias" :key="c.id" :value="c.id">{{ c.nombre }}</option></select>
        <select v-model="orden" class="input"><option value="recientes">Más recientes</option><option value="monto">Mayor monto</option></select>
        <button class="btn-primary" @click="sheet = false">Aplicar</button>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import api from '../services/api'
import { numero } from '../utils/formato'
type Mov = { id: string; tipo: string; monto: number; fecha: string; descripcion: string; categoria_id?: string; cuenta_id?: string; categoria?: string; cuenta?: string }
const filtro = ref('todos'); const q = ref(''); const mes = ref(new Date().toISOString().slice(0, 7))
const items = ref<Mov[]>([]); const cuentas = ref<{ id: string; nombre: string }[]>([]); const categorias = ref<{ id: string; nombre: string }[]>([])
const sheet = ref(false); const cuentaId = ref(''); const categoriaId = ref(''); const orden = ref('recientes')
const loading = ref(true)
const label = (f: string) => f === 'todos' ? 'Todos' : f === 'ingreso' ? 'Ingresos' : 'Gastos'
const fmt = (n: number) => numero(n)
const cuentaNombre = computed(() => cuentas.value.find((c) => c.id === cuentaId.value)?.nombre ?? 'todas')
const categoriaNombre = computed(() => categorias.value.find((c) => c.id === categoriaId.value)?.nombre ?? 'todas')
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
  const [cu, ca] = await Promise.all([api.get('/cuentas'), api.get('/categorias', { params: { solo_activas: false } })])
  cuentas.value = cu.data; categorias.value = ca.data; await cargar()
})
watch([filtro, cuentaId, categoriaId, orden], cargar)
let t: ReturnType<typeof setTimeout>
watch(q, () => { clearTimeout(t); t = setTimeout(cargar, 350) })
</script>

<style>
.chip { border: 1px solid var(--navy); background: var(--surface); color: var(--navy); border-radius: 99px; padding: 8px 14px; font-weight: 700; }
.chip.on { background: var(--navy); color: #fff; }
.link { background: none; border: 0; color: var(--ink-soft); margin-top: 8px; }
.row { display: flex; align-items: center; gap: 12px; padding: 12px 2px; border-bottom: 1px solid var(--line); }
.btn-new { background: var(--mint); color: var(--navy); border: 0; border-radius: 12px; padding: 10px 14px; font-weight: 800; }
.sheet-back { position: fixed; inset: 0; background: rgba(5,11,59,.45); z-index: 30; display: flex; align-items: flex-end; }
.sheet { background: var(--surface); color: var(--ink); width: 100%; border-radius: 20px 20px 0 0; padding: 18px; display: grid; gap: 10px; }
</style>
