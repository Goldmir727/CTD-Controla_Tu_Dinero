<template>
  <main class="page">
    <h2>¿Cuánto dinero tienes hoy?</h2>
    <p class="sub">Lo usamos solo para calcular tu <strong>DISPONIBLE</strong> inicial. Nada se comparte. Ver <a href="#" @click.prevent="$router.push('/datos')">Política de Datos</a>.</p>
    <p class="sub">¿Solo quieres ver tus ingresos y gastos del mes? Déjalo en <strong>0</strong>, funciona igual.</p>
    <div style="display: flex; gap: 8px; margin: 12px 0">
      <button :class="['chip', modo === 'todo_junto' ? 'on' : '']" @click="modo = 'todo_junto'">Todo en una cuenta</button>
      <button :class="['chip', modo === 'separadas' ? 'on' : '']" @click="modo = 'separadas'">En cuentas separadas</button>
    </div>
    <NumeroInput v-if="modo === 'todo_junto'" v-model="total" placeholder="Total actual (ej: 2.000.000)" />
    <div v-if="modo === 'separadas'" style="display: grid; gap: 8px">
      <p class="sub">Escribe cada parte y <strong>la app suma por ti</strong>. Sin restas ni cuadres.</p>
      <div v-for="(c, i) in cuentas" :key="i" class="grid-2">
        <input v-model="c.nombre" placeholder="Ej. Banco" class="input" />
        <NumeroInput v-model="c.monto" placeholder="Monto" />
      </div>
      <button class="link" @click="cuentas.push({ nombre: '', tipo: 'banco', monto: 0 })">+ Agregar otra cuenta</button>
      <div class="card">
        <div class="eyebrow">TOTAL CALCULADO</div>
        <div class="display" style="font-size: 32px">${{ fmt(suma) }}</div>
      </div>
    </div>
    <button class="btn-primary" style="margin-top: 12px" @click="guardar">Continuar</button>
    <p v-if="e" class="alert">{{ e }}</p>
    <button v-if="yaHecho" class="btn-mint" style="margin-top: 8px" @click="$router.push('/inicio')">Ir a mi app</button>
    <p class="sub">Podrás crear más cuentas después: se restan del total original automáticamente.</p>
  </main>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import NumeroInput from '../components/NumeroInput.vue'
import api from '../services/api'
import { numero } from '../utils/formato'
import { useAuth } from '../stores/auth'
const router = useRouter()
const auth = useAuth()
const yaHecho = ref(false)
const total = ref<number | null>(0); const modo = ref<'todo_junto' | 'separadas'>('todo_junto')
const cuentas = ref<{ nombre: string; tipo: string; monto: number | null }[]>([{ nombre: 'Banco', tipo: 'banco', monto: 0 }])
const e = ref('')
const suma = computed(() => cuentas.value.reduce((a, c) => a + (c.monto || 0), 0))
const fmt = (n: number | null) => numero(n)
async function guardar() {
  e.value = ''
  yaHecho.value = false
  try {
    await api.post('/onboarding/completar', { modo: modo.value, total: total.value ?? 0, cuentas: modo.value === 'separadas' ? cuentas.value.map((c) => ({ ...c, monto: c.monto || 0 })) : [] })
    auth.setOnboarding(true)
    router.push('/inicio')
  } catch (err: unknown) {
    const r = (err as { response?: { status?: number; data?: { detail?: string } } }).response
    if (r?.status === 409) {
      yaHecho.value = true
      e.value = r?.data?.detail ?? 'Este paso ya está completado.'
    } else e.value = r?.data?.detail ?? 'Revisa los datos e intenta de nuevo.'
  }
}
</script>
<style>.chip{border:1px solid var(--navy);background:var(--surface);color:var(--navy);border-radius:99px;padding:8px 14px;font-weight:700}.chip.on{background:var(--navy);color:#fff}.sub{font-size:13px;opacity:.65}.link{background:none;border:0;color:var(--ink-soft)}</style>
