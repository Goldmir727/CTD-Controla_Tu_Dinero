<template>
  <main class="page">
    <h2>Nuevo movimiento</h2>
    <p v-if="error" id="nm-error" ref="errorBox" class="alert" role="alert" aria-live="assertive">
      {{ error }}
    </p>
    <form @submit.prevent="guardar" style="display: grid; gap: 14px">
      <div class="field">
        <span class="etiqueta">Tipo de movimiento</span>
        <div class="tipo-switch" role="group" aria-label="Tipo de movimiento">
          <button type="button" :class="['chip', form.tipo === 'gasto' ? 'on' : '']"
                  :aria-pressed="form.tipo === 'gasto'" @click="form.tipo = 'gasto'">Gasto</button>
          <button type="button" :class="['chip', form.tipo === 'ingreso' ? 'on' : '']"
                  :aria-pressed="form.tipo === 'ingreso'" @click="form.tipo = 'ingreso'">Ingreso</button>
        </div>
      </div>

      <div class="field">
        <label for="nm-monto">Monto</label>
        <NumeroInput id="nm-monto" v-model="form.monto" placeholder="Ej. 100.000"
                     :aria-describedby="error ? 'nm-error' : undefined" required />
      </div>

      <div class="field">
        <label for="nm-desc">Descripción</label>
        <input id="nm-desc" v-model="form.descripcion" placeholder="Ej. Almuerzo con amigos" class="input" />
      </div>

      <div class="field">
        <label for="nm-cuenta">Cuenta</label>
        <select id="nm-cuenta" v-model="form.cuenta_id" class="input" required
                :aria-describedby="error ? 'nm-error' : undefined">
          <option value="" disabled>Elige una cuenta</option>
          <option v-for="c in cuentas" :key="c.id" :value="c.id">{{ c.nombre }}</option>
        </select>
      </div>

      <div class="field">
        <label for="nm-categoria">Categoría</label>
        <select id="nm-categoria" v-model="form.categoria_id" class="input" required
                :aria-describedby="error ? 'nm-error' : undefined">
          <option value="" disabled>Elige una categoría</option>
          <option v-for="c in categoriasFiltradas" :key="c.id" :value="c.id">{{ c.nombre }}</option>
        </select>
      </div>

      <div class="field">
        <label for="nm-metodo">Método de pago <span class="sub">(opcional)</span></label>
        <select id="nm-metodo" v-model="form.metodo_id" class="input">
          <option value="">Sin método</option>
          <option v-for="m in metodos" :key="m.id" :value="m.id">{{ m.nombre }}</option>
        </select>
      </div>

      <div class="field">
        <label for="nm-fecha">Fecha</label>
        <input id="nm-fecha" v-model="form.fecha" type="date" class="input" required
               :aria-describedby="error ? 'nm-error' : undefined" />
      </div>

      <button class="btn-primary" :disabled="loading || !valido">
        {{ loading ? 'Guardando…' : 'Guardar' }}
      </button>
    </form>
  </main>
</template>
<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NumeroInput from '../components/NumeroInput.vue'
import api from '../services/api'
const router = useRouter()
const route = useRoute()
const loading = ref(false)
const error = ref('')
const errorBox = ref<HTMLElement | null>(null)
const cuentas = ref<{ id: string; nombre: string }[]>([])
const categorias = ref<{ id: string; nombre: string; tipo: string }[]>([])
const metodos = ref<{ id: string; nombre: string }[]>([])
const form = reactive({ tipo: 'gasto', monto: null as number | null, descripcion: '', fecha: new Date().toISOString().slice(0, 10), cuenta_id: '', categoria_id: '', metodo_id: '' })

/**
 * El menu del boton flotante abre esta vista con ?tipo=ingreso o ?tipo=gasto,
 * pero el tipo estaba fijo en 'gasto' y la query nunca se leia: al elegir
 * "+ Ingreso" el formulario ofrecia "Gasto" y habia que cambiarlo a mano.
 */
onMounted(() => {
  if (route.query.tipo === 'ingreso' || route.query.tipo === 'gasto') form.tipo = route.query.tipo
  // Desde el calendario se entra con la fecha ya elegida. Solo se acepta una
  // fecha valida y no futura: el backend rechaza el futuro y no tiene sentido
  // ofrecer un formulario que va a fallar al guardar.
  const f = String(route.query.fecha ?? '')
  if (/^\d{4}-\d{2}-\d{2}$/.test(f) && f <= new Date().toISOString().slice(0, 10)) form.fecha = f
})

/**
 * Las categorias se filtran por tipo, asi que al cambiar de Gasto a Ingreso la
 * categoria elegida puede dejar de existir en la lista. Sin limpiarla se
 * mandaba un id de gasto dentro de un ingreso.
 */
watch(() => form.tipo, () => {
  const sigueValida = categorias.value.some(
    (c) => c.id === form.categoria_id && (c.tipo === form.tipo || c.tipo === 'ambos'),
  )
  if (!sigueValida) form.categoria_id = ''
})

const categoriasFiltradas = computed(() =>
  categorias.value.filter((c) => c.tipo === form.tipo || c.tipo === 'ambos')
)
const valido = computed(() => form.monto && form.monto > 0 && form.fecha && form.cuenta_id && form.categoria_id)

onMounted(async () => {
  try {
    const [cu, ca, me] = await Promise.all([
      api.get('/cuentas'), api.get('/categorias', { params: { solo_activas: true } }), api.get('/metodos-pago')
    ])
    cuentas.value = cu.data
    categorias.value = ca.data
    metodos.value = me.data
    if (cuentas.value[0]) form.cuenta_id = cuentas.value[0].id
  } catch { mostrarError('No se pudieron cargar cuentas/categorías. Reintenta.') }
})

function mostrarError(msg: string) {
  error.value = msg
  void nextTick(() => errorBox.value?.scrollIntoView({ block: 'center', behavior: 'smooth' }))
}

function detalle422(e: unknown): string {
  const r = (e as { response?: { data?: { detail?: unknown; field_errors?: Record<string, string> } } }).response?.data
  if (!r) return 'No se pudo guardar. Revisa monto, fecha y cuenta.'
  if (r.field_errors) return Object.entries(r.field_errors).map(([k, v]) => `${k}: ${v}`).join(' · ')
  if (Array.isArray(r.detail)) return r.detail.map((d: { loc?: string[]; msg?: string }) => `${d.loc?.slice(-1)}: ${d.msg}`).join(' · ')
  if (typeof r.detail === 'string') return r.detail
  return 'Datos inválidos (422). Revisa los campos.'
}

async function guardar() {
  loading.value = true; error.value = ''
  try {
    const payload = { ...form, categoria_id: form.categoria_id || null, metodo_id: form.metodo_id || null }
    await api.post('/movimientos', payload, { headers: { 'Idempotency-Key': crypto.randomUUID() } })
    router.push('/inicio')
  } catch (e: unknown) { mostrarError(detalle422(e)) }
  finally { loading.value = false }
}
</script>
<style scoped>
/* Mismo control en dos toques que en Movs y Plan, en vez de un desplegable con
   dos opciones que ademas salia con el valor equivocado. */
.tipo-switch { display: flex; gap: 8px; }
.tipo-switch .chip { flex: 1; }
.etiqueta { font-size: 13px; font-weight: 700; color: var(--ink-soft); }
</style>
