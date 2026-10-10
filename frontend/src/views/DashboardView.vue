<template>
  <main class="page rise">
    <p class="eyebrow">{{ saludo }}, {{ nombre }}</p>
    <section class="card-featured" style="margin: 12px 0 16px">
      <div class="eyebrow" style="color: #B9C2E0">DISPONIBLE</div>
      <div class="big-number">${{ fmt(disponible) }}</div>
      <div class="delta" v-if="tasa !== null"><i :class="['bi', tasa >= 0 ? 'bi-arrow-up' : 'bi-arrow-down']"></i> {{ Math.abs(tasa) }}% este mes</div>
      <span class="glow-line"></span>
    </section>

    <section class="card">
      <div class="eyebrow">BALANCE DE {{ mesLabel }}</div>
      <div class="big-number" style="font-size: 32px">{{ balance >= 0 ? '+' : '−' }}${{ fmt(Math.abs(balance)) }}</div>
      <hr class="divider" />
      <div class="grid-2">
        <div><div class="eyebrow">INGRESOS</div><strong>${{ fmt(ingresos) }}</strong></div>
        <div><div class="eyebrow">GASTOS</div><strong>${{ fmt(gastos) }}</strong></div>
      </div>
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
import { onMounted, ref } from 'vue'
import api from '../services/api'
import { numero } from '../utils/formato'
const nombre = ref('')
const disponible = ref(0)
const ingresos = ref(0); const gastos = ref(0); const balance = ref(0)
const tasa = ref<number | null>(null)
const metas = ref<{ id: string; nombre: string; porcentaje: number; faltante: number; ahorro_requerido_mensual: number | null; imagen_url?: string | null }[]>([])
const mes = new Date().toISOString().slice(0, 7)
const fmt = (n: number) => numero(n)
const mesLabel = new Date().toLocaleDateString('es-CO', { month: 'long' }).toUpperCase()
const saludo = new Date().getHours() < 12 ? 'Buenos días' : new Date().getHours() < 19 ? 'Buenas tardes' : 'Buenas noches'
onMounted(async () => {
  const [me, cuentas, resumen, met] = await Promise.all([
    api.get('/auth/me').catch(() => null),
    api.get('/cuentas').catch(() => null),
    api.get('/resumen', { params: { mes } }).catch(() => null),
    api.get('/metas').catch(() => null)
  ])
  if (me) nombre.value = me.data.nombre?.split(' ')[0] ?? ''
  if (cuentas) disponible.value = cuentas.data.reduce((a: number, c: { saldo_actual: number }) => a + Number(c.saldo_actual), 0)
  if (resumen) { ingresos.value = resumen.data.ingresos; gastos.value = resumen.data.gastos; balance.value = resumen.data.balance_mes; tasa.value = resumen.data.tasa_ahorro }
  if (met) metas.value = [...met.data.filter((m: { faltante: number }) => m.faltante > 0), ...met.data.filter((m: { faltante: number }) => m.faltante <= 0)].slice(0, 2)
})
</script>
