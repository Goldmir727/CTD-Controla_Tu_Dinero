<template>
  <main class="page">
    <h2>Plan PRO</h2>

    <!-- Ya lo tiene: no se le vende nada -->
    <section v-if="info?.es_pro" class="card pro-ok">
      <div class="eyebrow">PLAN ACTIVO</div>
      <h3>Ya tienes PRO</h3>
      <p class="sub">
        Se renueva solo cada mes. Tu acceso sigue hasta el
        <strong>{{ info.vence ? fechaCorta(info.vence) : 'final del periodo' }}</strong>.
      </p>
      <button v-if="info.estado !== 'cancelada'" class="btn-ghost" @click="cancelar">
        No quiero renovar
      </button>
      <p v-else class="sub">
        No se renovará. Vas a poder usar PRO hasta el
        <strong>{{ info.vence ? fechaCorta(info.vence) : 'final del periodo' }}</strong>
        y después vuelves a la versión gratis. Tus datos se quedan.
      </p>
      <button class="link" @click="$router.push('/inicio')">Volver al inicio</button>
    </section>

    <!-- Lo que ofrece -->
    <template v-else>
      <section class="card">
        <div class="precio">
          <strong>{{ money(info?.precio_mes) }}</strong>
          <span class="sub">al mes</span>
        </div>
        <p class="sub">
          Se renueva solo. Si no te sirve, cancela cuando quieras y conservas el
          acceso hasta que acabe lo que ya pagaste.
        </p>
        <button v-if="info?.habilitado" class="btn-primary" :disabled="pagando" @click="pagar">
          <span v-if="pagando" class="spinner"></span>Activar PRO
        </button>
        <p v-else-if="info" class="alert">
          El pago todavía no está disponible. Tus datos exportables siguen
          libres: usa el Excel o el JSON desde Ajustes.
        </p>
        <p v-if="error" class="alert">{{ error }}</p>
      </section>

      <section class="card">
        <div class="eyebrow">QUÉ SE DESBLOQUEA</div>
        <ul class="lista">
          <li v-for="x in info?.incluye ?? []" :key="x.titulo">
            <i class="bi bi-check-lg"></i>
            <div><strong>{{ x.titulo }}</strong><span class="sub">{{ x.detalle }}</span></div>
          </li>
        </ul>
      </section>

      <section class="card">
        <div class="eyebrow">LO QUE SIGUE SIENDO GRATIS</div>
        <ul class="lista">
          <li v-for="x in info?.gratis ?? []" :key="x.titulo">
            <i class="bi bi-check-lg"></i>
            <div><strong>{{ x.titulo }}</strong><span class="sub">{{ x.detalle }}</span></div>
          </li>
        </ul>
        <p class="sub" v-if="info">
          Hoy tienes {{ info.tu_plan.asesor_dia }} preguntas al asesor y
          {{ info.tu_plan.captura_dia }} capturas al día.
        </p>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import { fechaCorta, dinero } from '../utils/formato'

type Item = { titulo: string; detalle: string }
type Info = {
  precio_mes: number
  moneda: string
  habilitado: boolean
  es_pro: boolean
  plan: string
  vence: string | null
  estado: string | null
  incluye: Item[]
  gratis: Item[]
  tu_plan: { asesor_dia: number; captura_dia: number }
}

const router = useRouter()
const info = ref<Info | null>(null)
const pagando = ref(false)
const error = ref('')

function money(v?: number) {
  return v == null ? '' : dinero(v, info.value?.moneda ?? 'COP')
}

onMounted(async () => {
  try {
    const { data } = await api.get('/billing/plan')
    info.value = data
  } catch {
    error.value = 'No se pudo cargar el plan. Reintenta.'
  }
})

/**
 * El cobro lo hace Wompi en su pagina; aqui solo se registra el intento y se
 * manda al usuario. El PRO lo activa el webhook, no esta pantalla: si el pago
 * falla a medio camino, el usuario no queda con PRO sin haber pagado.
 */
async function pagar() {
  pagando.value = true
  error.value = ''
  try {
    const { data } = await api.post('/billing/checkout')
    window.location.href = data.url
  } catch (e: unknown) {
    const r = (e as { response?: { status?: number; data?: { detail?: string } } }).response
    error.value = r?.data?.detail ?? 'No se pudo iniciar el pago. Reintenta.'
    pagando.value = false
  }
}

async function cancelar() {
  try {
    await api.post('/billing/cancelar', {})
    const { data } = await api.get('/billing/plan')
    info.value = data
  } catch {
    error.value = 'No se pudo cancelar. Reintenta.'
  }
}
</script>

<style scoped>
.pro-ok h3 { margin: 6px 0 8px; }
.precio { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }
.precio strong { font-size: 34px; font-weight: 800; letter-spacing: -0.02em; }
.lista { list-style: none; margin: 10px 0 0; padding: 0; display: grid; gap: 12px; }
.lista li { display: flex; gap: 10px; align-items: flex-start; }
.lista i { color: var(--mint-dark); font-size: 16px; margin-top: 2px; }
.lista div { display: grid; gap: 2px; }
.link { background: none; border: 0; color: var(--mint-dark); font-weight: 700; padding: 8px 0 0; cursor: pointer; }
</style>