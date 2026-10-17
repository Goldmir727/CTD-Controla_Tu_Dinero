<template>
  <main class="page rise dashboard">
    <p class="eyebrow">{{ saludo }}, {{ nombre }}</p>
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
// El backend ya decide el corte segun la preferencia del usuario; aqui solo se
// usa para las rotulos. El fallback es MENSUAL porque es el default del producto.
const usaQuincena = computed(() => revision.value?.usa_quincena ?? false)

onMounted(async () => {
  const [me, cuentas, resumen, met, perfiles, rev] = await Promise.all([
    api.get('/auth/me').catch(() => null),
    api.get('/cuentas').catch(() => null),
    api.get('/resumen', { params: { mes } }).catch(() => null),
    api.get('/metas').catch(() => null),
    api.get('/perfiles').catch(() => null),
    api.get('/asesor/revision').catch(() => null)
  ])
  if (me) {
    nombre.value = me.data.nombre?.split(' ')[0] ?? ''
    moneda.value = me.data.moneda ?? 'COP'
    avisoMoneda.value = me.data.aviso_moneda ?? ''
  }
  if (cuentas) disponible.value = cuentas.data.reduce((a: number, c: { saldo_actual: number }) => a + Number(c.saldo_actual), 0)
  if (resumen) { ingresos.value = resumen.data.ingresos; gastos.value = resumen.data.gastos; balance.value = resumen.data.balance_mes; tasa.value = resumen.data.tasa_ahorro }
  if (met) metas.value = [...met.data.filter((m: { faltante: number }) => m.faltante > 0), ...met.data.filter((m: { faltante: number }) => m.faltante <= 0)].slice(0, 2)
  if (rev) revision.value = rev.data
  const negocio = (perfiles?.data?.items ?? []).find((p: { tipo: string }) => p.tipo === 'negocio')
  negocioId.value = negocio?.id ?? null
  if (negocio) {
    const r = await api.get(`/perfiles/${negocio.id}/mezcla`).catch(() => null)
    if (r) mezcla.value = r.data
  }
})
</script>

<style scoped>
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
</style>
