<script setup lang="ts">
/** Agenda: los movimientos en vista de calendario, día por día.

 *  Por qué existe: Movimientos es una lista, y una lista no deja ver los huecos
 *  (el domingo sin nada, la semana que se fue en salidas). Aquí el mes se lee de
 *  un vistazo y al tocar un día se abre lo que pasó ese día, sin cambiar de
 *  pantalla.

 *  Es gratis a propósito: revisar tus propios movimientos no es un reporte
 *  avanzado. El mapa de calor y las comparativas siguen siendo PRO en Datos.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import { dinero, firmado, mesEs, numero, locale } from '../utils/formato'

type Mov = {
  id: string
  tipo: 'ingreso' | 'gasto'
  monto: number
  descripcion: string
  categoria: string | null
  cuenta: string | null
}

type Dia = {
  dia: number
  ingresos: number
  gastos: number
  balance: number
  movimientos: Mov[]
  fijos_previstos: { id: string; nombre: string; tipo: string; monto: number; etiqueta: string }[]
  fijos_registrados: { id: string; nombre: string; tipo: string; monto: number; etiqueta: string }[]
}

type MesCalendario = {
  mes: string
  anio: number
  mes_num: number
  ultimo_dia: number
  inicio_semana: number
  dias: Dia[]
  dias_con_movimiento: number
  totales: { ingresos: number; gastos: number }
}

const router = useRouter()
const SEMANA = ['L', 'M', 'X', 'J', 'V', 'S', 'D']
const hoy = new Date()
const mes = ref(hoy.toISOString().slice(0, 7))
const datos = ref<MesCalendario | null>(null)
const cargando = ref(false)
const error = ref('')
const seleccion = ref<number>(hoy.getDate())
const moneda = ref('COP')

const dias = computed(() => datos.value?.dias ?? [])
const inicio = computed(() => datos.value?.inicio_semana ?? 0)
const esMesActual = computed(() => mes.value === hoy.toISOString().slice(0, 7))
const hoyNum = computed(() => (esMesActual.value ? new Date().getDate() : -1))
const diaSel = computed(() => dias.value.find((d) => d.dia === seleccion.value) ?? null)
const totales = computed(() => datos.value?.totales ?? { ingresos: 0, gastos: 0 })
const balanceMes = computed(() => totales.value.ingresos - totales.value.gastos)
const fmt = (n: number) => dinero(n, moneda.value)

/** Para la celda: el monto tiene que caber en ~50px. Sin símbolo, con signo. */
function corto(n: number) {
  const abs = Math.abs(n)
  const signo = n < 0 ? '−' : '+'
  if (abs >= 1_000_000) return signo + numero(abs / 1_000_000, 1) + 'M'
  if (abs >= 1000) return signo + numero(abs / 1000, 0) + 'k'
  return signo + numero(abs)
}

function fechaLarga(dia: number) {
  if (!datos.value) return ''
  const txt = new Date(datos.value.anio, datos.value.mes_num - 1, dia)
    .toLocaleDateString(locale(), { weekday: 'long', day: 'numeric', month: 'long' })
  // Solo la primera letra: `text-transform: capitalize` en CSS ponia "24 De
  // Octubre" con mayuscula en cada palabra.
  return txt.charAt(0).toUpperCase() + txt.slice(1)
}

async function cargar() {
  cargando.value = true
  error.value = ''
  try {
    const { data } = await api.get<MesCalendario>('/calendario', { params: { mes: mes.value } })
    datos.value = data
    extractFijos(data)
    // Al abrir, el día de hoy manda; en otro mes, el primer día con algo.
    if (data.mes === hoy.toISOString().slice(0, 7)) {
      seleccion.value = new Date().getDate()
    } else {
      const conMov = data.dias.find((d) => d.movimientos.length)
      seleccion.value = conMov?.dia ?? 1
    }
  } catch {
    error.value = 'No pude cargar el mes. Intenta de nuevo.'
  } finally {
    cargando.value = false
  }
}

/** Extraer los fijos previstos y registrados de cada día */
function extractFijos(data: MesCalendario): void {
  if (!data || !data.dias) return
  data.dias.forEach((d) => {
    d.fijos_previstos = (d.fijos_previstos || []).map((f: any) => ({
      id: f.id,
      nombre: f.nombre,
      tipo: f.tipo,
      monto: f.monto,
      etiqueta: f.etiqueta,
    }))
    d.fijos_registrados = (d.fijos_registrados || []).map((f: any) => ({
      id: f.id,
      nombre: f.nombre,
      tipo: f.tipo,
      monto: f.monto,
      etiqueta: f.etiqueta,
    }))
  })
}

function mover(delta: number) {
  const [a, m] = mes.value.split('-').map(Number)
  const d = new Date(a, m - 1 + delta, 1)
  mes.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function irHoy() {
  mes.value = new Date().toISOString().slice(0, 7)
  seleccion.value = new Date().getDate()
}

/** Registrar algo en el día elegido: la fecha ya viene puesta. */
function registrar(dia: number) {
  router.push({ path: '/movimientos/nuevo', query: { fecha: `${mes.value}-${String(dia).padStart(2, '0')}` } })
}

watch(mes, cargar)
onMounted(async () => {
  try {
    const { data } = await api.get('/auth/me')
    moneda.value = data.moneda ?? 'COP'
  } catch { /* seguimos con COP */ }
  await cargar()
})
</script>

<template>
  <main class="page agenda">
    <p class="eyebrow">CALENDARIO</p>
    <div class="cab">
      <h2>Tu mes, día por día</h2>
      <div class="mes-nav" role="group" aria-label="Cambiar de mes">
        <button class="flecha" aria-label="Mes anterior" @click="mover(-1)">
          <i class="bi bi-chevron-left"></i>
        </button>
        <strong aria-live="polite">{{ mesEs(mes) }}</strong>
        <button class="flecha" aria-label="Mes siguiente" @click="mover(1)">
          <i class="bi bi-chevron-right"></i>
        </button>
        <button v-if="!esMesActual" class="hoy" @click="irHoy">Hoy</button>
      </div>
    </div>

    <section class="card resumen" v-if="datos">
      <div><span class="eyebrow">INGRESOS</span><strong class="pos">{{ fmt(totales.ingresos) }}</strong></div>
      <div><span class="eyebrow">GASTOS</span><strong class="neg">{{ fmt(totales.gastos) }}</strong></div>
      <div>
        <span class="eyebrow">BALANCE</span>
        <strong :class="balanceMes >= 0 ? 'pos' : 'neg'">{{ firmado(balanceMes, moneda) }}</strong>
      </div>
    </section>

    <div v-if="cargando" class="skel" style="height: 320px; border-radius: 20px"></div>

    <template v-else-if="datos">
      <section class="card cal">
        <div class="semana" aria-hidden="true">
          <span v-for="(s, i) in SEMANA" :key="i">{{ s }}</span>
        </div>
        <div class="rejilla" role="grid" aria-label="Días del mes">
          <span v-for="n in inicio" :key="'h' + n" class="hueco" aria-hidden="true"></span>
          <button
            v-for="d in dias"
            :key="d.dia"
            role="gridcell"
            class="dia"
            :class="{
              sel: d.dia === seleccion,
              hoy: d.dia === hoyNum,
              lleno: d.movimientos.length > 0 || (d.fijos_previstos.length || d.fijos_registrados.length) > 0
            }"
            :aria-label="`Día ${d.dia}: ${d.movimientos.length} ${d.movimientos.length === 1 ? 'movimiento' : 'movimientos'}, ${d.fijos_previstos.length} previstos, ${d.fijos_registrados.length} registrados`"
            :aria-selected="d.dia === seleccion"
            @click="seleccion = d.dia"
          >
            <span class="num">{{ d.dia }}</span>
            <span v-if="d.fijos_previstos.length || d.fijos_registrados.length" class="agenda-detalle">
              <span v-if="d.fijos_registrados.length" class="badge badge-registrados">
                {{ d.fijos_registrados.length }} {{ d.fijos_registrados.length === 1 ? 'registrado' : 'registrados' }}
              </span>
              <span v-if="d.fijos_previstos.length" class="badge-badge-previstos">
                <i class="bi bi-calendar" aria-hidden="true" style="margin-right: 4px; font-size: 10px;"></i>
                {{ d.fijos_previstos.length }} {{ d.fijos_previstos.length === 1 ? 'previsto' : 'previstos' }}
              </span>
            </span>
            <span v-if="d.balance" class="flujo">{{ corto(d.balance) }}</span>
          </button>
        </div>
      </section>

      <section v-if="diaSel" class="card detalle">
        <header class="det-cab">
          <div>
            <strong class="fecha">{{ fechaLarga(diaSel.dia) }}</strong>
            <span class="sub">
              {{ diaSel.movimientos.length }}
              {{ diaSel.movimientos.length === 1 ? 'movimiento' : 'movimientos' }}
              <template v-if="diaSel.movimientos.length">
                · {{ diaSel.balance >= 0 ? '+' : '−' }}{{ fmt(Math.abs(diaSel.balance)) }}
              </template>
            </span>
          </div>
          <div v-if="diaSel.fijos_previstos.length || diaSel.fijos_registrados.length" class="agenda-fijos-resumen">
            <span v-if="diaSel.fijos_registrados.length" class="agenda-fijos-badge agenda-fijos-registrados">{{ diaSel.fijos_registrados.length }} {{ diaSel.fijos_registrados.length === 1 ? 'registrado' : 'registrados' }}</span>
            <span v-if="diaSel.fijos_previstos.length" class="agenda-fijos-badge agenda-fijos-previstos"><i class="bi bi-calendar" aria-hidden="true" style="margin-right: 4px; font-size: 9px;"></i>{{ diaSel.fijos_previstos.length }} {{ diaSel.fijos_previstos.length === 1 ? 'previsto' : 'previstos' }}</span>
          </div>
          <button class="link" @click="registrar(diaSel.dia)">+ Registrar</button>
        </header>

        <ul v-if="diaSel.movimientos.length" class="lista">
          <li v-for="m in diaSel.movimientos" :key="m.id">
            <span :class="['icono', m.tipo]">
              <i :class="['bi', m.tipo === 'ingreso' ? 'bi-arrow-up' : 'bi-arrow-down']"></i>
            </span>
            <span class="quien">
              <span>{{ m.descripcion || m.categoria || 'Movimiento' }}</span>
              <small>{{ [m.categoria, m.cuenta].filter(Boolean).join(' · ') }}</small>
            </span>
            <strong :class="m.tipo === 'ingreso' ? 'pos' : 'neg'">
              {{ m.tipo === 'ingreso' ? '+' : '−' }}{{ fmt(m.monto) }}
            </strong>
          </li>
        </ul>

        <ul v-if="diaSel.fijos_previstos.length" class="lista lista-fijos">
          <li v-for="f in diaSel.fijos_previstos" :key="f.id">
            <span class="icono fijo-previsto">
              <i class="bi bi-calendar-fill" aria-hidden="true"></i>
            </span>
            <span class="quien">
              <span>{{ f.nombre }}</span>
              <small>{{ f.etiqueta }} · {{ f.tipo === 'ingreso' ? 'ingreso' : 'gasto' }}</small>
            </span>
            <strong :class="f.tipo === 'ingreso' ? 'pos' : 'neg'">
              {{ f.tipo === 'ingreso' ? '+' : '−' }}{{ fmt(f.monto) }}
            </strong>
          </li>
        </ul>

        <ul v-if="diaSel.fijos_registrados.length" class="lista lista-fijos">
          <li v-for="f in diaSel.fijos_registrados" :key="f.id">
            <span class="icono fijo-registrado">
              <i class="bi bi-calendar-check-fill" aria-hidden="true"></i>
            </span>
            <span class="quien">
              <span>{{ f.nombre }}</span>
              <small>{{ f.etiqueta }} · {{ f.tipo === 'ingreso' ? 'ingreso' : 'gasto' }}</small>
            </span>
            <strong :class="f.tipo === 'ingreso' ? 'pos' : 'neg'">
              {{ f.tipo === 'ingreso' ? '+' : '−' }}{{ fmt(f.monto) }}
            </strong>
          </li>
        </ul>

        <div v-if="!diaSel.movimientos.length && !diaSel.fijos_previstos.length && !diaSel.fijos_registrados.length" class="vacio">
          <i class="bi bi-calendar-x"></i>
          <p class="sub">Nada registrado el {{ diaSel.dia }}. Si pasó algo, anótalo y el calendario lo acomoda.</p>
        </div>
      </section>
    </template>

    <p v-if="error" class="alert" role="alert">{{ error }}</p>
    <p class="sub pie" v-if="datos">
      {{ datos.dias_con_movimiento }} {{ datos.dias_con_movimiento === 1 ? 'día con movimiento' : 'días con movimientos' }}
      de {{ datos.ultimo_dia }}. Los fijos se ven en Inicio y en Movimientos › Fijos.
    </p>
  </main>
</template>

<style scoped>
.cab { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 4px 0 12px; }
.cab h2 { font-size: 22px; margin: 0; flex: 1; min-width: 200px; }
.mes-nav { display: flex; align-items: center; gap: 4px; background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 4px; }
.mes-nav strong { font-size: 13.5px; padding: 0 6px; white-space: nowrap; }
.flecha, .hoy {
  border: 0; background: none; cursor: pointer; min-width: 36px; min-height: 36px;
  border-radius: 10px; color: var(--ink); display: inline-flex; align-items: center; justify-content: center;
}
.flecha:hover, .hoy:hover { background: var(--navy-soft); }
.hoy { font-weight: 800; font-size: 12.5px; padding: 0 10px; color: var(--mint-text); }
.flecha:focus-visible, .hoy:focus-visible, .dia:focus-visible { outline: none; box-shadow: 0 0 0 3px rgba(0, 255, 171, .3); }

.resumen { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px; }
.resumen strong { display: block; font-size: 16px; margin-top: 2px; font-variant-numeric: tabular-nums; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.resumen .eyebrow { font-size: 10.5px; }

.cal { padding: 14px; }
.semana, .rejilla { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 4px; }
.semana { margin-bottom: 6px; }
.semana span { text-align: center; font-size: 11px; font-weight: 700; color: var(--ink-soft); }
.hueco { min-height: 44px; }
.dia {
  min-height: 52px; min-width: 0; padding: 4px 2px; border: 1px solid transparent; border-radius: 10px;
  background: var(--bg-soft); color: var(--ink); cursor: pointer;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1px;
  font: inherit;
}
.dia.lleno { background: var(--mint-soft); border-color: rgba(0, 255, 171, .35); }
.dia.hoy .num { color: var(--mint-text); }
.dia.hoy { border-color: var(--mint-dark); }
.dia.sel { background: var(--navy); border-color: var(--navy); }
.dia.sel .num { color: #fff; }
.dia.sel .flujo { color: var(--mint); }
.num { font-size: 13px; font-weight: 700; line-height: 1.1; }
.flujo { font-size: 9.5px; font-weight: 700; letter-spacing: -.02em; color: var(--ink-soft); max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pos { color: var(--mint-text); }
.neg { color: var(--danger-text); }

.detalle { margin-top: 14px; }
.det-cab { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.det-cab .fecha { display: block; }
.det-cab .sub { display: block; margin-top: 2px; }
.lista { list-style: none; margin: 12px 0 0; padding: 0; }
.lista li { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--line); }
.lista li:last-child { border-bottom: 0; }
.icono { width: 32px; height: 32px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; flex: none; }
.icono.ingreso { background: var(--mint-tint); color: var(--mint-text); }
.icono.gasto { background: var(--danger-soft); color: var(--danger-text); }
.quien { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.quien > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.quien small { color: var(--ink-soft); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lista strong { font-variant-numeric: tabular-nums; white-space: nowrap; }
.vacio { text-align: center; padding: 18px 8px 6px; }
.vacio i { font-size: 26px; color: var(--ink-soft); }
.vacio p { margin: 8px auto 0; max-width: 34ch; }
.pie { margin-top: 12px; text-align: center; }

@media (min-width: 1000px) {
  .page.agenda { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, .65fr); gap: 0 20px; align-items: start; }
  .page.agenda > .eyebrow, .page.agenda > .cab, .page.agenda > .resumen, .page.agenda > .pie,
  .page.agenda > .alert, .page.agenda > .skel { grid-column: 1 / -1; }
  .detalle { margin-top: 0; position: sticky; top: 84px; }
  .dia { min-height: 64px; }
  .flujo { font-size: 10.5px; }
}

/* Fijo styles for agenda */
.badge {
  display: inline-block;
  padding: 2px 6px;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  color: var(--ink);
  text-align: center;
  white-space: nowrap;
  vertical-align: middle;
  border-radius: 4px;
}
.badge-registrados {
  background: var(--danger-soft);
  color: var(--danger-text);
}
.badge-badge-previstos {
  background: var(--mint-soft);
  color: var(--mint-text);
}
.agenda-fijos-badge {
  display: inline-block;
  padding: 2px 6px;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  color: var(--ink);
  text-align: center;
  white-space: nowrap;
  vertical-align: middle;
  border-radius: 4px;
  margin-left: 4px;
}
.agenda-fijos-registrados {
  background: var(--danger-soft);
  color: var(--danger-text);
}
.agenda-fijos-previstos {
  background: var(--mint-soft);
  color: var(--mint-text);
}
.lista-fijos { margin-top: 10px; }
.lista-fijos li { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--line); }
.lista-fijos li:last-child { border-bottom: 0; }
.fijo-previsto { width: 32px; height: 32px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; flex: none; background: var(--mint-tint); color: var(--mint-text); }
.fijo-registrado { width: 32px; height: 32px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; flex: none; background: var(--danger-soft); color: var(--danger-text); }
.lista-fijos .quien > span { font-weight: 600; }
.lista-fijos small { font-size: 11.5px; }
</style>