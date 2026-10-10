<script setup lang="ts">
/** Datos: resumen del mes, distribución por categoría, evolución, fijos y calendario.
 *  Los bloques básicos son gratis; los detallados piden plan PRO (el backend
 *  responde 402 y acá mostramos el upsell en vez de un error seco). */
import { computed, onMounted, ref, watch } from 'vue'
import Grafico from '../components/Grafico.vue'
import api from '../services/api'
import { animacionesOff } from '../composables/usePerf'
import { dinero, mesEs, numero, porcentaje } from '../utils/formato'
import { PALETA, TEMA, colorPorIndice } from '../utils/paleta'

const TABS = [
  { id: 'resumen', label: 'Resumen' },
  { id: 'categorias', label: 'Categorías' },
  { id: 'comparativa', label: 'Evolución' },
  { id: 'fijos', label: 'Fijos' },
  { id: 'calendario', label: 'Calendario' }
] as const
type Tab = (typeof TABS)[number]['id']

type DistItem = { nombre: string; total: number; porcentaje: number }
type EvoluItem = { mes: string; ingresos: number; gastos: number; balance_mes: number; tasa_ahorro: number }
type FijoItem = { mes: string; ingresos: number; fijos: number; variables: number; total_gastos: number; ratio_fijo: number }
type DiaItem = { dia: number; ingresos: number; gastos: number; balance: number }

const tab = ref<Tab>('resumen')
const mes = ref(new Date().toISOString().slice(0, 7))
const moneda = ref('COP')
const cargando = ref(false)
const pro = ref(false)
const mensajePro = ref('')

const resumen = ref<{ ingresos: number; gastos: number; balance_mes: number; tasa_ahorro: number } | null>(null)
const dist = ref<DistItem[]>([])
const evolucion = ref<EvoluItem[]>([])
const fijos = ref<FijoItem[]>([])
const fijosMeta = ref<{ fijos_mes: number; ratio_fijo_promedio: number; estimacion: boolean } | null>(null)
const calendario = ref<{ dias: DiaItem[]; ultimo_dia: number; dias_con_gasto: number } | null>(null)
const metas = ref<{ nombre: string; objetivo: number; ahorrado: number }[]>([])

const fmt = (n: number) => dinero(n, moneda.value)
const fmtLargo = (n: number) => numero(n, 0)

async function pedir<T>(ruta: string): Promise<T | null> {
  try {
    const { data } = await api.get<T>(ruta)
    return data
  } catch (e: unknown) {
    const st = (e as { response?: { status?: number; data?: { detail?: string } } }).response?.status
    if (st === 402) {
      pro.value = true
      mensajePro.value = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? ''
    }
    return null
  }
}

async function cargar() {
  cargando.value = true
  const mesQ = `?mes=${mes.value}`
  // Los básicos siempre; los detallados solo si el usuario tiene PRO.
  const [r, d, e] = await Promise.all([
    pedir<{ ingresos: number; gastos: number; balance_mes: number; tasa_ahorro: number }>(`/resumen${mesQ}`),
    pedir<DistItem[]>(`/reportes/distribucion?${mesQ.slice(1)}&tipo=gasto`),
    pedir<{ items: EvoluItem[]; mensaje: string }>(`/reportes/evolucion?meses=6&hasta=${mes.value}`)
  ])
  resumen.value = r
  dist.value = (d ?? []).slice(0, 8)
  evolucion.value = e?.items ?? []
  if (!pro.value) await cargarDetallado()
  else { fijos.value = []; calendario.value = null }
  cargando.value = false
}

async function cargarDetallado() {
  const mesQ = `mes=${mes.value}`
  const [f, c] = await Promise.all([
    pedir<{ items: FijoItem[]; fijos_mes: number; ratio_fijo_promedio: number; estimacion: boolean }>(
      '/reportes/fijos?meses=6'),
    pedir<{ dias: DiaItem[]; ultimo_dia: number; dias_con_gasto: number; metas: typeof metas.value }>(
      `/reportes/calendario?${mesQ}`)
  ])
  fijos.value = f?.items ?? []
  fijosMeta.value = f ? { fijos_mes: f.fijos_mes, ratio_fijo_promedio: f.ratio_fijo_promedio, estimacion: f.estimacion } : null
  calendario.value = c ? { dias: c.dias, ultimo_dia: c.ultimo_dia, dias_con_gasto: c.dias_con_gasto } : null
  metas.value = c?.metas ?? []
}
onMounted(async () => {
  try {
    const { data } = await api.get('/auth/me')
    moneda.value = data.moneda ?? 'COP'
    pro.value = data.plan === 'pro' || !!data.capacidades?.reportes_detallados
  } catch { /* seguimos con COP */ }
  await cargar()
})
watch(mes, cargar)

// ---- Opciones de grafico ----
const opcionDona = computed(() => {
  const datos = dist.value
  if (!datos.length) return { series: [] }
  return {
    tooltip: {
      trigger: 'item',
      // Formato es-CO en el tooltip: el valor por defecto de ECharts pone "1.5M".
      valueFormatter: (v: unknown) => fmt(Number(v))
    },
    legend: { show: false },
    series: [{
      type: 'pie',
      radius: ['52%', '76%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: true,
      padAngle: 1.5,
      itemStyle: { borderRadius: 6, borderColor: 'transparent' },
      // Etiquetas FUERA del anillo con conector, como en el gráfico de referencia.
      label: {
        show: true,
        position: 'outside',
        formatter: (p: { name: string; percent: number }) =>
          `${p.name}\n${numero(p.percent, 0)}%`,
        color: TEMA.inkSoft,
        fontSize: 11,
        lineHeight: 15
      },
      labelLine: { length: 12, length2: 16, smooth: false },
      emphasis: { scale: true, scaleSize: 6 },
      data: datos.map((d, i) => ({
        name: d.nombre,
        value: d.total,
        itemStyle: { color: colorPorIndice(i) }
      }))
    }]
  }
})

const opcionComparativa = computed(() => {
  const items = evolucion.value
  if (!items.length) return { series: [] }
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
      valueFormatter: (v: unknown) => fmt(Number(v)) },
    legend: { bottom: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10 },
    grid: { left: 8, right: 8, top: 12, bottom: 34, containLabel: true },
    xAxis: { type: 'category', data: items.map((i) => mesEs(i.mes).slice(0, 3)) },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => numero(v / 1000, 0) + 'k' } },
    series: [
      { name: 'Ingresos', type: 'bar', data: items.map((i) => i.ingresos),
        itemStyle: { color: TEMA.mintDark, borderRadius: [4, 4, 0, 0] }, barMaxWidth: 22 },
      { name: 'Gastos', type: 'bar', data: items.map((i) => i.gastos),
        itemStyle: { color: TEMA.navy, borderRadius: [4, 4, 0, 0] }, barMaxWidth: 22 },
      { name: 'Balance', type: 'line', data: items.map((i) => i.balance_mes),
        smooth: true, symbolSize: 7,
        lineStyle: { width: 3, color: TEMA.warning },
        itemStyle: { color: TEMA.warning } }
    ]
  }
})

const opcionFijos = computed(() => {
  const items = fijos.value
  if (!items.length) return { series: [] }
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
      valueFormatter: (v: unknown) => fmt(Number(v)) },
    legend: { bottom: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10 },
    grid: { left: 8, right: 8, top: 12, bottom: 34, containLabel: true },
    xAxis: { type: 'category', data: items.map((i) => mesEs(i.mes).slice(0, 3)) },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => numero(v / 1000, 0) + 'k' } },
    series: [
      { name: 'Fijos', type: 'bar', stack: 'g', data: items.map((i) => i.fijos),
        itemStyle: { color: TEMA.navy }, barMaxWidth: 26 },
      { name: 'Variables', type: 'bar', stack: 'g', data: items.map((i) => i.variables),
        itemStyle: { color: TEMA.mintDark, borderRadius: [4, 4, 0, 0] }, barMaxWidth: 26 }
    ]
  }
})

const opcionCalendario = computed(() => {
  const dias = calendario.value?.dias ?? []
  if (!dias.length) return { series: [] }
  const max = Math.max(...dias.map((d) => d.gastos), 1)
  return {
    tooltip: {
      formatter: (p: { dataIndex: number }) => {
        const d = dias[p.dataIndex]
        return `${mesEs(mes.value)} · día ${d.dia}<br/>Ingresos: <b>${fmt(d.ingresos)}</b><br/>Gastos: <b>${fmt(d.gastos)}</b>`
      }
    },
    grid: { left: 8, right: 8, top: 12, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: dias.map((d) => String(d.dia)),
      axisLabel: { fontSize: 9, interval: 1 }
    },
    yAxis: {
      type: 'value',
      max: max * 1.12,
      axisLabel: { formatter: (v: number) => numero(v / 1000, 0) + 'k' }
    },
    series: [{
      type: 'bar',
      data: dias.map((d) => ({
        value: d.gastos,
        itemStyle: { color: d.gastos > 0 ? TEMA.mintDark : 'transparent', borderRadius: [3, 3, 0, 0] }
      })),
      barMaxWidth: 12
    }]
  }
})
</script>

<template>
  <div class="page">
    <p class="eyebrow">DATOS</p>
    <h2>Lo que está pasando con tu dinero</h2>

    <div class="chips" role="tablist">
      <button v-for="t in TABS" :key="t.id" class="chip" :class="{ on: tab === t.id }"
              role="tab" :aria-selected="tab === t.id" @click="tab = t.id">
        {{ t.label }}
      </button>
    </div>

    <div v-if="pro" class="card pro">
      <i class="bi bi-lock-fill"></i>
      <div>
        <strong>Reportes detallados · PRO</strong>
        <p>{{ mensajePro || 'Activa tu plan PRO para ver fijos, calendario y comparativas completas.' }}</p>
      </div>
      <button class="btn-mint" @click="$router.push('/config')">Ver plan</button>
    </div>

    <div v-if="cargando" class="skel" style="height: 120px"></div>

    <!-- RESUMEN -->
    <template v-else-if="tab === 'resumen'">
      <div class="card-featured">
        <span class="eyebrow">BALANCE DE {{ mesEs(mes).toUpperCase() }}</span>
        <div class="big-number" :class="(resumen?.balance_mes ?? 0) >= 0 ? 't-pos' : 't-neg'">
          {{ fmt(resumen?.balance_mes ?? 0) }}
        </div>
        <div class="grid-2">
          <div><span class="sub">Ingresaste</span><strong class="amount t-pos">{{ fmt(resumen?.ingresos ?? 0) }}</strong></div>
          <div><span class="sub">Gastaste</span><strong class="amount t-neg">{{ fmt(resumen?.gastos ?? 0) }}</strong></div>
        </div>
        <p class="sub" v-if="resumen">Tasa de ahorro: {{ porcentaje(resumen.tasa_ahorro) }}</p>
      </div>

      <div class="card">
        <h3>Distribución de gastos</h3>
        <Grafico v-if="dist.length" :opcion="opcionDona" :alto="280" />
        <p v-else class="empty">Todavía no hay gastos registrados este mes.</p>
        <ul class="leyenda">
          <li v-for="(d, i) in dist" :key="d.nombre">
            <span class="punto" :style="{ background: colorPorIndice(i) }"></span>
            <span class="nom">{{ d.nombre }}</span>
            <span class="val">{{ porcentaje(d.porcentaje) }}</span>
          </li>
        </ul>
      </div>

      <div class="card">
        <h3>Ingresos vs gastos · últimos 6 meses</h3>
        <Grafico v-if="evolucion.length" :opcion="opcionComparativa" :alto="240" />
      </div>
    </template>

    <!-- CATEGORÍAS -->
    <template v-else-if="tab === 'categorias'">
      <div class="card">
        <h3>En qué se va tu plata</h3>
        <p class="sub">{{ mesEs(mes) }} · total {{ fmt(resumen?.gastos ?? 0) }}</p>
        <Grafico v-if="dist.length" :opcion="opcionDona" :alto="300" />
        <div v-if="dist.length" class="ranking">
          <div v-for="(d, i) in dist" :key="d.nombre" class="fila">
            <span class="punto" :style="{ background: colorPorIndice(i) }"></span>
            <span class="nom">{{ d.nombre }}</span>
            <span class="barra"><span :style="{ width: Math.min(d.porcentaje, 100) + '%', background: colorPorIndice(i) }"></span></span>
            <span class="val">{{ fmtLargo(d.total) }}</span>
          </div>
        </div>
      </div>
    </template>

    <!-- EVOLUCIÓN -->
    <template v-else-if="tab === 'comparativa'">
      <div class="card">
        <h3>Comparativa mes a mes</h3>
        <Grafico v-if="evolucion.length" :opcion="opcionComparativa" :alto="280" />
        <table v-if="evolucion.length" class="tabla">
          <thead><tr><th>Mes</th><th>Ingresos</th><th>Gastos</th><th>Balance</th></tr></thead>
          <tbody>
            <tr v-for="i in evolucion" :key="i.mes">
              <td>{{ mesEs(i.mes) }}</td>
              <td class="t-pos">{{ fmt(i.ingresos) }}</td>
              <td class="t-neg">{{ fmt(i.gastos) }}</td>
              <td :class="i.balance_mes >= 0 ? 't-pos' : 't-neg'">{{ fmt(i.balance_mes) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- FIJOS -->
    <template v-else-if="tab === 'fijos'">
      <div v-if="!pro" class="card empty">Activa PRO para ver el desglose de fijos vs variables.</div>
      <template v-else>
        <div v-if="fijosMeta" class="card-featured">
          <span class="eyebrow">GASTOS FIJOS AL MES</span>
          <div class="big-number">{{ fmt(fijosMeta.fijos_mes) }}</div>
          <p class="sub">
            {{ porcentaje(fijosMeta.ratio_fijo_promedio) }} de lo que gastás es fijo ·
            <em>estimación</em>
          </p>
        </div>
        <div class="card">
          <h3>Fijos vs variables</h3>
          <Grafico v-if="fijos.length" :opcion="opcionFijos" :alto="260" />
          <p v-else class="empty">Marcá tus gastos fijos en Plan › Fijos para ver este gráfico.</p>
        </div>
        <div v-if="fijos.length" class="card">
          <h3>Tus fijos declarados</h3>
          <ul class="leyenda">
            <li v-for="f in fijos" :key="f.mes">
              <span class="nom">{{ mesEs(f.mes) }}</span>
              <span class="val">{{ porcentaje(f.ratio_fijo) }} fijo</span>
            </li>
          </ul>
        </div>
      </template>
    </template>

    <!-- CALENDARIO -->
    <template v-else-if="tab === 'calendario'">
      <div v-if="!pro" class="card empty">Activa PRO para ver el calendario de gastos.</div>
      <template v-else>
        <div v-if="calendario" class="card">
          <h3>Gasto por día · {{ mesEs(mes) }}</h3>
          <p class="sub">{{ calendario.dias_con_gasto }} días con gasto de {{ calendario.ultimo_dia }}</p>
          <Grafico :opcion="opcionCalendario" :alto="220" />
        </div>
        <div v-if="metas.length" class="card">
          <h3>Metas en el mes</h3>
          <ul class="leyenda">
            <li v-for="m in metas" :key="m.nombre">
              <span class="nom">{{ m.nombre }}</span>
              <span class="val">{{ fmt(m.ahorrado) }} / {{ fmt(m.objetivo) }}</span>
            </li>
          </ul>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
.chips { display: flex; gap: 8px; overflow-x: auto; padding: 12px 0 14px; scrollbar-width: none; }
.chips::-webkit-scrollbar { display: none; }
.chip { flex: 0 0 auto; }
h3 { font-size: 15px; margin: 0 0 10px; }

.leyenda { list-style: none; margin: 14px 0 0; padding: 0; }
.leyenda li { display: flex; align-items: center; gap: 8px; padding: 7px 0; font-size: 14px; border-bottom: 1px solid var(--line); }
.leyenda li:last-child { border-bottom: 0; }
.leyenda .nom { flex: 1; color: var(--ink); }
.leyenda .val { color: var(--ink-soft); font-variant-numeric: tabular-nums; }
.punto { width: 10px; height: 10px; border-radius: 3px; flex: 0 0 auto; }

.ranking { margin-top: 16px; }
.fila { display: flex; align-items: center; gap: 8px; padding: 8px 0; font-size: 14px; border-bottom: 1px solid var(--line); }
.fila:last-child { border-bottom: 0; }
.fila .nom { width: 84px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fila .barra { flex: 1; height: 8px; background: var(--line); border-radius: 4px; overflow: hidden; }
.fila .barra span { display: block; height: 100%; border-radius: 4px; }
.fila .val { width: 74px; text-align: right; font-variant-numeric: tabular-nums; color: var(--ink-soft); }

.tabla { width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 13px; }
.tabla th, .tabla td { padding: 8px 4px; text-align: right; border-bottom: 1px solid var(--line); font-variant-numeric: tabular-nums; }
.tabla th:first-child, .tabla td:first-child { text-align: left; }
.tabla th { color: var(--ink-soft); font-weight: 600; }

.card.pro { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.card.pro i { font-size: 20px; color: var(--warning); }
.card.pro div { flex: 1; }
.card.pro p { margin: 4px 0 0; font-size: 13px; color: var(--ink-soft); }
</style>
