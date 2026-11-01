<template>
  <main class="page rise dashboard">
    <p class="eyebrow">{{ saludo }}, {{ nombre }}</p>
    <p v-if="datosDeCache || offlineSinCache" class="sub aviso-cache" role="status">
      <i class="bi bi-wifi-off" aria-hidden="true"></i>
      <span v-if="datosDeCache">Sin conexión: estas cifras son de tu última conexión. Puedes registrar movimientos y se enviarán al volver la red.</span>
      <span v-else>Sin conexión: no podemos cargar tus cifras ahora. Puedes seguir registrando movimientos; se enviarán al volver la red.</span>
    </p>
    <section class="card-featured" style="margin: 12px 0 16px">
      <div class="eyebrow" style="color: #B9C2E0">DISPONIBLE</div>
      <div class="big-number">{{ fmt(disponible) }} <span class="unidad">{{ cod }}</span></div>
      <div class="delta" v-if="tasa !== null"><i :class="['bi', tasa >= 0 ? 'bi-arrow-up' : 'bi-arrow-down']"></i> {{ Math.abs(tasa) }}% este mes</div>
      <span class="glow-line"></span>
    </section>

    <section v-if="mezcla && mezcla.hay_riesgo" class="card aviso-mezcla">
      <div class="mezcla-top">
        <i class="bi bi-exclamation-triangle-fill"></i>
        <div>
          <div class="eyebcla">{{ mezcla.perfil }} · POSIBLES MEZCLAS</div>
          <div style="font-weight: 700; font-size: 15px">
            Salió {{ dinero(mezcla.total) }} del negocio en gastos personales
          </div>
        </div>
      </div>
      <ul class="mezcla-lista">
        <li v-for="h in mezcla.hallazgos" :key="h.categoria + h.cuenta">
          <span>{{ h.categoria }}</span>
          <span class="sub">desde {{ h.cuenta }} · {{ h.movimientos }} mov.</span>
          <strong>{{ dinero(h.total) }}</strong>
        </li>
      </ul>
      <p class="sub">
        Si esas salidas son del negocio, déjalas aquí. Si son tuyas, muévelas a tu
        cuenta personal para no ensuciar el balance del negocio.
      </p>
      <button class="btn-mint" @click="$router.push('/config')">Revisar perfiles</button>
    </section>

    <section v-if="avisoMoneda" class="card aviso-moneda">
      <i class="bi bi-cash-coin"></i>
      <div>
        <strong>Todas tus cifras están en {{ moneda }}.</strong>
        <p class="sub">
          {{ avisoMoneda }}
          <button class="link" @click="$router.push('/config')">Cambiar</button>
        </p>
      </div>
    </section>

<!--
    El balance va ANTES que la proyección, y no por estética: la proyección es
    una estimación que asume el ritmo actual, y el balance es lo que de verdad
    entró menos lo que salió. Arrancar por la estimación invita a leer
    "+8.167.200" como plata que uno tiene, y no la tiene.
-->
<section class="card-featured card-balance">
      <div class="eyebrow">BALANCE DE {{ mesLabel }}</div>
      <div class="big-number" style="font-size: 32px">{{ balance >= 0 ? '+' : '−' }}${{ fmt(Math.abs(balance)) }}</div>
      <hr class="divider" />
      <div class="grid-2">
        <div><div class="eyebrow">INGRESOS</div><strong>${{ fmt(ingresos) }}</strong></div>
        <div><div class="eyebrow">GASTOS</div><strong>${{ fmt(gastos) }}</strong></div>
      </div>
    </section>

    <!-- Agenda diaria de fijos: lo que debía caer y lo ya registrado. -->
    <section v-if="diasAgenda.length" class="card agenda-card" data-tour="agenda">
      <div class="agenda-cab">
        <div>
          <div class="eyebrow">AGENDA DIARIA</div>
          <div class="agenda-sub">Fijos que debían caer este mes vs los ya registrados</div>
        </div>
        <div class="agenda-total-caja">
          <strong class="agenda-total">{{ totalFijos }}</strong>
          <div class="agenda-subt">{{ totalPrevistos }} previstos · {{ totalRegistrados }} registrados</div>
        </div>
      </div>

      <div v-if="totalFijos" class="agenda-grid">
        <div v-for="d in diasConFijos" :key="d.dia" class="agenda-dia">
          <div class="agenda-dia-num">{{ d.dia }}</div>
          <div class="agenda-dia-cuerpo">
            <div class="agenda-detalle">
              <span v-if="d.fijos_registrados.length" class="badge badge-registrados">
                {{ d.fijos_registrados.length }} {{ d.fijos_registrados.length === 1 ? 'registrado' : 'registrados' }}
              </span>
              <span v-if="d.fijos_previstos.length" class="badge badge-previstos">
                {{ d.fijos_previstos.length }} {{ d.fijos_previstos.length === 1 ? 'previsto' : 'previstos' }}
              </span>
            </div>
            <ul v-if="d.fijos_registrados.length">
              <li v-for="f in d.fijos_registrados" :key="f.id" class="agenda-item agenda-item-registrado">
                <span class="agenda-item-texto">{{ f.nombre }}</span>
                <span class="agenda-item-monto">{{ f.tipo === 'ingreso' ? '+' : '−' }}{{ fmt(f.monto) }}</span>
              </li>
            </ul>
            <ul v-if="d.fijos_previstos.length">
              <li v-for="f in d.fijos_previstos" :key="f.id" class="agenda-item agenda-item-previsto">
                <span class="agenda-item-texto">{{ f.nombre }}</span>
                <span class="agenda-item-monto">{{ f.tipo === 'ingreso' ? '+' : '−' }}{{ fmt(f.monto) }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      <div v-else class="agenda-vacio">
        Sin fijos próximos este mes.
      </div>
    </section>

<section v-if="revision" class="card revision" data-tour="quincena">
      <div class="revision-cab">
        <div>
          <div class="eyebrow">{{ revision.etiqueta_legible }}</div>
          <div class="revision-dia">
            día {{ revision.quincena.dias_transcurridos }} de {{ revision.quincena.dias_totales }}
          </div>
        </div>
<div class="revision-saldo">
      <div class="eyebrow proy"><i class="bi bi-graph-up"></i> Proyección</div>
      <strong :class="revision.proyeccion.saldo_al_cerrar >= 0 ? 'pos' : 'neg'">
        {{ revision.proyeccion.saldo_al_cerrar >= 0 ? '+' : '−' }}{{ fmt(Math.abs(revision.proyeccion.saldo_al_cerrar)) }}
        <span class="unidad">{{ cod }}</span>
      </strong>
      <div class="sub proy-pie">
        al {{ usaQuincena ? 'cerrar la quincena' : 'cerrar el mes' }}
      </div>
    </div>
      </div>

      <div class="revision-bar" :title="'Vas ' + revision.quincena.dias_transcurridos + ' de ' + revision.quincena.dias_totales + ' días ' + (usaQuincena ? 'de la quincena' : 'del mes')">
        <span :style="{ width: Math.round((revision.quincena.dias_transcurridos / revision.quincena.dias_totales) * 100) + '%' }"></span>
      </div>

      <div class="grid-2 revision-nums">
        <div>
          <div class="eyebrow">GASTADO</div>
          <strong>${{ fmt(revision.movimientos.gastos) }}</strong>
        </div>
        <div>
          <div class="eyebrow">FIJOS QUE VENCEN</div>
          <strong>${{ fmt(revision.fijos.gastos) }}</strong>
        </div>
      </div>

      <ul v-if="revision.fijos.items.length" class="revision-fijos">
        <li v-for="f in revision.fijos.items" :key="f.nombre">
          <span>{{ f.nombre }}</span>
          <span class="sub">día {{ f.dia }}<span v-if="f.veces > 1"> · ×{{ f.veces }}</span></span>
          <strong>${{ fmt(f.monto) }}</strong>
        </li>
      </ul>

      <div v-for="a in revision.alertas" :key="a.categoria_id" class="alerta-ritmo" data-tour="alerta">
        <i class="bi" :class="a.estado === 'excedido' ? 'bi-exclamation-octagon-fill' : 'bi-speedometer2'"></i>
        <p>{{ a.mensaje }}</p>
      </div>

<p v-if="revision.comparacion" class="sub revision-comp">
        {{ usaQuincena ? 'La ' : 'En ' }}{{ revision.comparacion.legible }} gastaste
        <strong>${{ fmt(revision.comparacion.gastos) }}</strong>
        <span :class="revision.movimientos.gastos > revision.comparacion.gastos ? 'neg' : 'pos'">
          ({{ revision.movimientos.gastos > revision.comparacion.gastos ? '+' : '−' }}${{ fmt(Math.abs(revision.movimientos.gastos - revision.comparacion.gastos)) }})
        </span>
      </p>

<p class="sub revision-nota">
        <i class="bi bi-info-circle"></i>
        La proyección asume tu ritmo actual y lo fijo que falta. No anticipa ingresos.
      </p>
    </section>

    <hr class="divider" />
    <div class="eyebrow">PRÓXIMAS METAS</div>
    <section v-if="!metas.length" class="card" style="margin-top: 8px">
      <p class="sub">Sin metas. Crea una en Plan para ver tu progreso aquí.</p>
    </section>
    <section v-for="m in metas" :key="m.id" class="card" style="margin-top: 8px">
      <div style="display: flex; gap: 10px; align-items: center">
        <img v-if="m.imagen_url" :src="m.imagen_url" :alt="m.nombre" style="width: 44px; height: 44px; object-fit: cover; border-radius: 12px; flex: none" />
        <div style="flex: 1">
          <div style="display: flex; justify-content: space-between"><span>{{ m.nombre }}</span><span>{{ Math.round(m.porcentaje) }}%</span></div>
          <div class="progress" style="margin-top: 8px"><span :style="{ width: Math.min(m.porcentaje, 100) + '%' }"></span></div>
        </div>
      </div>
      <p class="sub" v-if="m.faltante > 0">Te faltan ${{ fmt(m.faltante) }}<span v-if="m.ahorro_requerido_mensual != null"> · ${{ fmt(m.ahorro_requerido_mensual) }}/mes (estimación)</span><span v-else> · Sin fecha: aporta a tu ritmo</span></p>
      <p class="sub" v-else>¡Meta cumplida!</p>
    </section>
    <section class="card-featured" style="margin-top: 12px; cursor: pointer" @click="$router.push('/asesor')">
      <div class="eyebrow" style="color: var(--mint)">ASESOR IA · PRO</div>
      <div style="font-weight: 800; font-size: 17px">¿Cómo voy este mes? Pregunta con tus números.</div>
      <span class="glow-line"></span>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import api from '../services/api'
import { codigo, dinero, numero } from '../utils/formato'
const nombre = ref('')
const disponible = ref(0)
const ingresos = ref(0); const gastos = ref(0); const balance = ref(0)
const tasa = ref<number | null>(null)
const metas = ref<{ id: string; nombre: string; porcentaje: number; faltante: number; ahorro_requerido_mensual: number | null; imagen_url?: string | null }[]>([])
const mes = new Date().toISOString().slice(0, 7)
const fmt = (n: number) => numero(n)
const mesLabel = new Date().toLocaleDateString('es-CO', { month: 'long' }).toUpperCase()
const saludo = new Date().getHours() < 12 ? 'Buenos días' : new Date().getHours() < 19 ? 'Buenas tardes' : 'Buenas noches'

type Mezcla = {
  perfil: string
  hay_riesgo: boolean
  total: number
  hallazgos: { categoria: string; cuenta: string; total: number; movimientos: number }[]
  mensaje: string
}
const mezcla = ref<Mezcla | null>(null)
// Solo tiene sentido avisar si hay un Negocio configurado; si el usuario es
// personal, el aviso no aparecería nunca y el código sobraría.
const negocioId = ref<string | null>(null)
const moneda = ref('COP')
const cod = computed(() => codigo(moneda.value))
// El backend avisa cuando el pais no usa la moneda del usuario: es justo cuando
// un numero se puede leer como dinero que el usuario no tiene.
const avisoMoneda = ref('')

type AlertaRitmo = {
  categoria: string
  categoria_id: string
  estado: string
  porcentaje: number
  delta_puntos: number
  dias_transcurridos: number
  dias_periodo: number
  ritmo_diario: number
  ritmo_sostenible: number
  mensaje: string
}
type Revision = {
  etiqueta_legible: string
  usa_quincena: boolean
  quincena: { dias_transcurridos: number; dias_totales: number; dias_restantes: number }
  movimientos: { ingresos: number; gastos: number; balance: number; movimientos: number }
  fijos: { total: number; gastos: number; ingresos: number; items: { nombre: string; dia: number; veces: number; monto: number }[] }
  proyeccion: { saldo_al_cerrar: number; estimacion: boolean }
  comparacion: { legible: string; gastos: number } | null
  alertas: AlertaRitmo[]
  mensaje: string
}
const revision = ref<Revision | null>(null)
/** Sin red la API no responde y todos los Promise.all caian en null: la pantalla
 * mostraba $0 como si el usuario no tuviera nada. Se guarda el ultimo resumen
 * bueno y se marca como tal, en vez de inventar ceros.
 */
type ResumenCache = {
  disponible: number; ingresos: number; gastos: number; balance: number
  tasa: number | null; moneda: string; guardado: string
}
const CLAVE_CACHE = 'ctd-resumen-cache'
const datosDeCache = ref(false)
const offlineSinCache = ref(false)

function aplicarCache(): boolean {
  try {
    const c = JSON.parse(localStorage.getItem(CLAVE_CACHE) ?? 'null') as ResumenCache | null
    if (!c) return false
    disponible.value = c.disponible
    ingresos.value = c.ingresos
    gastos.value = c.gastos
    balance.value = c.balance
    tasa.value = c.tasa
    moneda.value = c.moneda || 'COP'
    datosDeCache.value = true
    return true
  } catch { return false }
}

function guardarCache() {
  try {
    localStorage.setItem(CLAVE_CACHE, JSON.stringify({
      disponible: disponible.value, ingresos: ingresos.value, gastos: gastos.value,
      balance: balance.value, tasa: tasa.value, moneda: moneda.value,
      guardado: new Date().toISOString(),
    }))
  } catch { /* almacenamiento lleno o bloqueado: la app sigue funcionando */ }
}

// El backend ya decide el corte segun la preferencia del usuario; aqui solo se
// usa para las rotulos. El fallback es MENSUAL porque es el default del producto.
const usaQuincena = computed(() => revision.value?.usa_quincena ?? false)
/** Agenda diaria: fijos previstos vs registrados por dia */
const totalPrevistos = ref(0)
const totalRegistrados = ref(0)
const totalFijos = computed(() => totalPrevistos.value + totalRegistrados.value)
type FijoAgenda = {
  id: string
  nombre: string
  tipo: string
  monto: number
  etiqueta?: string
}
type DiaAgenda = {
  dia: number
  fijos_registrados: FijoAgenda[]
  fijos_previstos: FijoAgenda[]
}
const diasAgenda = ref<DiaAgenda[]>([])
const diasConFijos = computed(() => diasAgenda.value.filter(
  (d) => d.fijos_previstos.length > 0 || d.fijos_registrados.length > 0,
))

onMounted(async () => {
  // Sin red se evita la ronda de peticiones que van a fallar y se usa la copia.
  if (!navigator.onLine) {
    if (!aplicarCache()) offlineSinCache.value = true
    return
  }
  const [me, cuentas, resumen, met, perfiles, rev, cal] = await Promise.all([
    api.get('/auth/me').catch(() => null),
    api.get('/cuentas').catch(() => null),
    api.get('/resumen', { params: { mes } }).catch(() => null),
    api.get('/metas').catch(() => null),
    api.get('/perfiles').catch(() => null),
    api.get('/asesor/revision').catch(() => null),
    api.get('/calendario', { params: { mes } }).catch(() => null)
  ])
  if (me) {
    nombre.value = me.data.nombre?.split(' ')[0] ?? ''
    moneda.value = me.data.moneda ?? 'COP'
    avisoMoneda.value = me.data.aviso_moneda ?? ''
  }
  if (cuentas) disponible.value = cuentas.data.reduce((a: number, c: { saldo_actual: number }) => a + Number(c.saldo_actual), 0)
  if (resumen) { ingresos.value = resumen.data.ingresos; gastos.value = resumen.data.gastos; balance.value = resumen.data.balance_mes; tasa.value = resumen.data.tasa_ahorro }
  // Si no llego nada (red caida a mitad de carga), se muestra lo ultimo bueno.
  if (!me && !cuentas && !resumen) {
    if (!aplicarCache()) offlineSinCache.value = true
  } else {
    guardarCache()
  }
  if (met) metas.value = [...met.data.filter((m: { faltante: number }) => m.faltante > 0), ...met.data.filter((m: { faltante: number }) => m.faltante <= 0)].slice(0, 2)
  // Una respuesta parcial (sin quincena) hacia estallar la vista entera al leer
  // revision.quincena.dias_transcurridos: Inicio se quedaba en blanco. Se exige
  // la forma minima antes de pintar la tarjeta.
  if (rev?.data?.quincena && rev.data.movimientos) revision.value = rev.data
  // PROCESAR DATOS DE LA AGENDA DIARIA
  if (cal && cal.data) {
    totalPrevistos.value = cal.data.resumen_fijos.total_previstos || 0
    totalRegistrados.value = cal.data.resumen_fijos.total_registrados || 0
    diasAgenda.value = cal.data.dias.map((d: any) => ({
      dia: d.dia,
      fijos_registrados: d.fijos_registrados || [],
      fijos_previstos: d.fijos_previstos || []
    }))
  }
  const negocio = (perfiles?.data?.items ?? []).find((p: { tipo: string }) => p.tipo === 'negocio')
  negocioId.value = negocio?.id ?? null
  if (negocio) {
    const r = await api.get(`/perfiles/${negocio.id}/mezcla`).catch(() => null)
    if (r) mezcla.value = r.data
  }
})
</script>

<style scoped>
.aviso-cache {
  display: flex; gap: 7px; align-items: flex-start; margin: 4px 0 0;
  padding: 9px 11px; border-radius: 12px;
  background: rgba(216, 154, 39, .10); border-left: 3px solid var(--warning);
  color: var(--warning-text); font-size: 12.5px; line-height: 1.4;
}
.aviso-cache i { flex: none; margin-top: 1px; }
.aviso-mezcla { border-left: 3px solid var(--warning); background: rgba(216,154,39,.07); }
.mezcla-top { display: flex; gap: 10px; align-items: flex-start; }
.mezcla-top i { font-size: 20px; color: var(--warning); margin-top: 2px; }
.mezcla-top .eyebcla { font-size: 11px; font-weight: 700; color: var(--warning); letter-spacing: .5px; }
.mezcla-lista { list-style: none; margin: 10px 0; padding: 0; }
.mezcla-lista li { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--line); font-size: 13px; }
.mezcla-lista li:last-child { border-bottom: 0; }
.mezcla-lista li span:first-child { flex: 1; font-weight: 600; }
.mezcla-lista li strong { font-variant-numeric: tabular-nums; }
.aviso-mezcla .btn-mint { margin-top: 8px; }

.revision { margin-top: 16px; }
.revision-cab { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.revision-dia { font-size: 15px; font-weight: 700; margin-top: 2px; }
.revision-saldo { text-align: right; }
.revision-saldo strong { font-size: 19px; font-variant-numeric: tabular-nums; }
/*
  La proyección se marca por fuera, no solo por el rotulo: el numero va en 19px
  y en verde, igual que un saldo de verdad. Un "proyeccion" en versalitas pasa
  inadvertido al lado de una cifra que el usuario lee de un vistazo, asi que el
  bloque lleva borde punteado y tono atenuado para que se lea como lo que es:
  una estimacion, no plata en la cuenta.
*/
.revision-saldo .proy { display: inline-flex; align-items: center; gap: 5px; color: var(--ink-soft); }
.revision-saldo .proy i { font-size: 12px; }
.revision-saldo strong { border-bottom: 1px dashed var(--line); display: inline-block; padding-bottom: 2px; }
.revision-saldo .proy-pie { margin-top: 3px; font-size: 11px; }
.revision-bar { height: 6px; background: var(--line); border-radius: 99px; margin: 12px 0 14px; overflow: hidden; }
.revision-bar span { display: block; height: 100%; background: var(--mint); border-radius: 99px; }
.revision-nums strong { font-size: 16px; font-variant-numeric: tabular-nums; }
.revision-fijos { list-style: none; margin: 10px 0 0; padding: 0; }
.revision-fijos li { display: flex; gap: 8px; align-items: baseline; padding: 6px 0; border-top: 1px solid var(--line); font-size: 13px; }
.revision-fijos li span:first-child { flex: 1; font-weight: 600; }
.revision-fijos li strong { font-variant-numeric: tabular-nums; }
.alerta-ritmo { display: flex; gap: 9px; align-items: flex-start; margin-top: 12px; padding: 10px 12px; border-radius: 12px; background: rgba(216,154,39,.10); border-left: 3px solid var(--warning); }
.alerta-ritmo i { color: var(--warning); font-size: 16px; margin-top: 2px; }
.alerta-ritmo p { margin: 0; font-size: 13px; line-height: 1.45; }
.revision-comp { margin-top: 12px; }
.revision-nota { margin-top: 8px; font-size: 11.5px; opacity: .75; }
.unidad { font-size: .52em; font-weight: 700; opacity: .6; letter-spacing: .04em; }
.pos { color: var(--mint); }
.neg { color: var(--danger); }
.aviso-moneda { display: flex; gap: 10px; align-items: flex-start; border-left: 3px solid var(--warning); background: rgba(216, 154, 39, .07); }
.aviso-moneda > i { font-size: 20px; color: var(--warning); margin-top: 1px; flex: none; }
.aviso-moneda p { margin: 4px 0 0; }
.aviso-moneda .link { padding: 0; font-size: 13px; text-decoration: underline; }

/* --- AGENDA DIARIA --- */
.agenda-card { margin-top: 16px; border-left: 4px solid var(--mint); }
.agenda-cab { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.agenda-cab .eyebrow { font-size: 13px; }
.agenda-sub { font-size: 12px; color: var(--ink-soft); margin-top: 2px; }
.agenda-total-caja { text-align: right; flex: none; }
.agenda-total { font-size: 22px; font-weight: 800; color: var(--ink); line-height: 1; }
.agenda-subt { font-size: 11px; color: var(--ink-soft); margin-top: 4px; white-space: nowrap; }
.agenda-grid { display: flex; flex-direction: column; gap: 0; }
.agenda-dia { display: grid; grid-template-columns: 38px minmax(0, 1fr); gap: 10px; align-items: start; padding: 10px 0; border-top: 1px solid var(--line); text-align: left; }
.agenda-dia:first-child { border-top: 0; padding-top: 0; }
.agenda-dia-num { font-size: 18px; font-weight: 800; color: var(--mint-text); line-height: 1.25; text-align: center; }
.agenda-dia-cuerpo { min-width: 0; }
.agenda-detalle { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 4px; }
.badge { display: inline-block; padding: 2px 7px; border-radius: 99px; font-size: 10.5px; font-weight: 700; }
.badge-registrados { background: var(--mint-tint); color: var(--mint-text); border: 1px solid rgba(34,197,94,.35); }
.badge-previstos { background: rgba(216,154,39,.14); color: var(--warning-text); border: 1px solid rgba(216,154,39,.35); }
.agenda-dia ul { list-style: none; margin: 0; padding: 0; }
.agenda-item { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; padding: 3px 0; font-size: 12.5px; }
.agenda-item + .agenda-item { border-top: 1px dashed var(--line); }
.agenda-item-texto { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.agenda-item-monto { flex: none; font-variant-numeric: tabular-nums; font-weight: 600; }
.agenda-item-registrado, .agenda-item-registrado .agenda-item-monto { color: var(--mint-text); }
.agenda-item-previsto, .agenda-item-previsto .agenda-item-monto { color: var(--warning-text); }
.agenda-vacio { text-align: center; padding: 18px 8px; color: var(--ink-soft); font-size: 13px; }

</style>
