<template>
  <section>
    <section v-if="resumenFijos && resumenFijos.cantidad" class="card" style="margin-bottom: 12px">
      <div class="eyebrow">FIJOS DEL MES</div>
      <div class="grid-2" style="margin-top: 6px">
        <div>
          <div class="sub">Entran</div>
          <strong style="color: var(--mint-text)">${{ fmt(resumenFijos.ingresos_fijos_mes) }}</strong>
        </div>
        <div>
          <div class="sub">Salen</div>
          <strong style="color: var(--danger-text)">${{ fmt(resumenFijos.gastos_fijos_mes) }}</strong>
        </div>
      </div>
      <div v-if="resumenFijos.ratio_fijo != null" class="sub" style="margin-top: 8px">
        El {{ resumenFijos.ratio_fijo }}% de lo que gastas es fijo. Si sube, tu margen
        desaparece aunque el saldo final se vea bien.
      </div>
    </section>

    <div style="display: flex; justify-content: flex-end; margin-bottom: 8px">
      <button class="btn-new" :aria-expanded="showForm" @click="alternarForm">
        {{ showForm ? 'Cancelar' : '+ Nuevo fijo' }}
      </button>
    </div>

    <form v-if="showForm" @submit.prevent="guardarFijo" class="card" style="display: grid; gap: 12px">
      <div class="field">
        <span class="etiqueta">Tipo</span>
        <div role="group" aria-label="Tipo de fijo" style="display: flex; gap: 8px">
          <button type="button" :class="['chip', nf.tipo === 'gasto' ? 'on' : '']" :aria-pressed="nf.tipo === 'gasto'" @click="nf.tipo = 'gasto'">Sale</button>
          <button type="button" :class="['chip', nf.tipo === 'ingreso' ? 'on' : '']" :aria-pressed="nf.tipo === 'ingreso'" @click="nf.tipo = 'ingreso'">Entra</button>
        </div>
      </div>
      <div class="field">
        <label for="nf-nombre">Nombre</label>
        <input id="nf-nombre" v-model="nf.nombre" :placeholder="nf.tipo === 'gasto' ? 'Ej. Arriendo' : 'Ej. Salario'" class="input" required />
      </div>
      <div class="field">
        <label for="nf-monto">Monto</label>
        <NumeroInput id="nf-monto" v-model="nf.monto" placeholder="Ej. 1.200.000" required />
      </div>
      <div style="display: flex; gap: 8px; align-items: end">
        <div class="field" style="flex: 1">
          <label for="nf-frecuencia">Frecuencia</label>
          <select id="nf-frecuencia" v-model="nf.frecuencia" class="input" @change="alCambiarFrecuencia">
            <option value="mensual">Cada mes</option>
            <option value="quincenal">Cada 15 días</option>
            <option value="semanal">Cada semana</option>
          </select>
        </div>
        <!-- Un pago semanal no cae en un día del mes: cae el mismo día de la
             semana. Pedir "día 18" para "me pagan cada domingo" era pedir un
             dato que no significa nada y que se corre de día al mes siguiente. -->
        <div v-if="nf.frecuencia === 'semanal'" class="field" style="width: 150px">
          <label for="nf-dia-semana">Día</label>
          <select id="nf-dia-semana" v-model.number="nf.dia_semana" class="input">
            <option v-for="(d, i) in DIAS" :key="d" :value="i">{{ d }}</option>
          </select>
        </div>
        <div v-else class="field" style="width: 110px">
          <label for="nf-dia">Día</label>
          <input id="nf-dia" v-model.number="nf.dia" type="number" min="1" max="31" class="input" />
        </div>
      </div>
      <p class="sub" style="margin: 0">{{ textoCuando }}</p>
      <div class="field">
        <label for="nf-categoria">Categoría</label>
        <select id="nf-categoria" v-model="nf.categoria_id" class="input">
          <option value="">Sin categoría</option>
          <option v-for="c in catsPara(nf.tipo)" :key="c.id" :value="c.id">{{ c.nombre }}</option>
        </select>
      </div>
      <div class="field">
        <label for="nf-cuenta">Cuenta</label>
        <select id="nf-cuenta" v-model="nf.cuenta_id" class="input">
          <option value="">Sin cuenta</option>
          <option v-for="c in cuentas" :key="c.id" :value="c.id">{{ c.nombre }}</option>
        </select>
      </div>
      <button class="btn-primary">{{ editando ? 'Guardar cambios' : 'Guardar fijo' }}</button>
    </form>

    <div v-if="!fijos.length" class="card" style="margin-top: 10px">
      <p class="sub">
        Sin gastos fijos todavía. Sirven para que el motor separe lo que siempre pagas de lo
        variable y no te diga "te alcanza" cuando en realidad no.
      </p>
    </div>

    <div v-for="f in fijos" :key="f.id" class="card" style="margin-top: 10px" :style="f.activo ? '' : 'border-style: dashed'">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px">
        <div style="min-width: 0">
          <strong>{{ f.nombre }}</strong>
          <div class="sub">
            <span class="pill-fr" :class="f.frecuencia">{{ cuando(f) }}</span>
            <span v-if="f.proxima" class="sub"> · próxima: {{ fechaCorta(f.proxima) }}</span>
            <span v-if="f.categoria"> · {{ f.categoria }}</span>
            <span v-if="f.frecuencia !== 'mensual'"> · equivale a ${{ fmt(f.monto_mes) }}/mes</span>
          </div>
        </div>
        <strong :style="f.tipo === 'ingreso' ? 'color:var(--mint-text)' : 'color:var(--danger-text)'">
          {{ f.tipo === 'ingreso' ? '+' : '−' }}${{ fmt(f.monto) }}
        </strong>
      </div>
      <div style="display: flex; gap: 10px; margin-top: 10px; align-items: center">
        <button class="link" @click="editarFijo(f)">Editar</button>
        <button class="link" @click="toggleFijo(f)">{{ f.activo ? 'Pausar' : 'Activar' }}</button>
        <button class="link" @click="eliminarFijo(f.id)">Eliminar</button>
      </div>
    </div>
    <p v-if="error" class="alert" role="alert" aria-live="assertive">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import NumeroInput from './NumeroInput.vue'
import api from '../services/api'
import { numero } from '../utils/formato'
import { confirmar } from '../composables/useConfirm'
import { useToast } from '../composables/useToast'

/** Ingresos y gastos fijos, con su frecuencia. Vive en Movimientos (desde Plan)
 *  porque un fijo se declara y se pasa a revisar como lo demas que entra y sale. */
type Cat = { id: string; nombre: string; tipo: string }
const toast = useToast()
const showForm = ref(false)
const error = ref('')

function alternarForm() {
  showForm.value = !showForm.value
  if (!showForm.value) cerrarFormFijo()
}

type Fijo = {
  id: string; nombre: string; tipo: 'ingreso' | 'gasto'; monto: number; monto_mes: number
  dia: number; dia_semana?: number | null; etiqueta?: string | null; proxima?: string | null
  frecuencia: string; activo: boolean; cuenta_id?: string | null
  categoria_id?: string | null; categoria?: string | null
}
// 0 = lunes ... 6 = domingo, igual que en el backend.
const DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
const DIAS_PLURAL = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábados', 'domingos']
type ResumenFijos = {
  cantidad: number; ingresos_fijos_mes: number; gastos_fijos_mes: number
  neto_fijo_mes: number; ratio_fijo: number | null
}
const fijos = ref<Fijo[]>([])
const resumenFijos = ref<ResumenFijos | null>(null)
const cats = ref<Cat[]>([])
const cuentas = ref<{ id: string; nombre: string }[]>([])
const editando = ref<string | null>(null)
const nf = reactive({
  nombre: '', tipo: 'gasto' as 'gasto' | 'ingreso', monto: null as number | null,
  dia: 1, dia_semana: null as number | null, frecuencia: 'mensual',
  categoria_id: '', cuenta_id: ''
})
const fmt = (n: number) => numero(n)

// Mismo copo de siempre: hoy, en el dia de la semana que se esta eligiendo.
function alCambiarFrecuencia() {
  if (nf.frecuencia === 'semanal' && nf.dia_semana == null) {
    nf.dia_semana = (new Date().getDay() + 6) % 7
  }
}

// La frecuencia explicada con las fechas reales, no con la jerga: "el 20 y el
// 5 de cada mes" se entiende; "quincenal desde el 20" hay que traducirlo.
const textoCuando = computed(() => {
  if (nf.frecuencia === 'semanal') {
    return `Se cobra o paga todos los ${DIAS_PLURAL[nf.dia_semana ?? 0]}.`
  }
  const dia = nf.dia || '—'
  if (nf.frecuencia === 'quincenal') {
    const otro = nf.dia > 15 ? nf.dia - 15 : nf.dia + 15
    return `Se cobra o paga el ${dia} y el ${otro} de cada mes.`
  }
  return `Se cobra o paga el día ${dia} de cada mes.`
})

function fechaCorta(iso: string) {
  const [a, m, d] = iso.split('-')
  return `${d}/${m}/${a.slice(2)}`
}

function catsPara(tipo: string) {
  return cats.value.filter((c) => c.tipo === tipo || c.tipo === 'ambos')
}

// "el día 20", "quincenal", etc. Sin esto el usuario tiene que traducir la
// frecuencia a un calendario mental, que es justo lo que la app hace por él.
function cuando(f: Fijo) {
  // El backend ya manda la etiqueta legible ("cada domingo"); el calculo local
  // queda solo para respuestas viejas en cache.
  if (f.etiqueta) return f.etiqueta
  const dia = f.dia
  if (f.frecuencia === 'semanal') return `cada 7 días desde el ${dia}`
  if (f.frecuencia === 'quincenal') return `el ${dia} y el ${dia > 15 ? dia - 15 : dia + 15} de cada mes`
  return `el día ${dia} de cada mes`
}

async function guardarFijo() {
  error.value = ''
  const cuerpo = {
    nombre: nf.nombre.trim(), tipo: nf.tipo, monto: nf.monto,
    dia: Math.max(1, Math.min(31, nf.dia || 1)), frecuencia: nf.frecuencia,
    dia_semana: nf.frecuencia === 'semanal' ? nf.dia_semana : null,
    categoria_id: nf.categoria_id || null, cuenta_id: nf.cuenta_id || null
  }
  try {
    if (editando.value) await api.patch(`/recurrentes/${editando.value}`, cuerpo)
    else await api.post('/recurrentes', cuerpo)
    alternarForm()
    await cargar()
  } catch (e: any) {
    // El backend responde cosas utiles ("La categoría 'Comida' no aplica a
    // ingresos"); se muestran tal cual en vez de un "no se pudo" genérico.
    error.value = e?.response?.data?.detail ?? 'No se pudo guardar el fijo.'
  }
}
function editarFijo(f: Fijo) {
  editando.value = f.id
  // Un semanal viejo no tiene dia de la semana guardado. Se propone el del dia
  // que ya usa, para que el select no muestre "lunes" con el campo vacio y
  // para que guardar sin tocar nada no lo convierta en otra cosa.
  let diaSemana = f.dia_semana ?? null
  if (f.frecuencia === 'semanal' && diaSemana == null) {
    const hoy = new Date()
    const ultimo = new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0).getDate()
    const ancla = new Date(hoy.getFullYear(), hoy.getMonth(), Math.min(f.dia, ultimo))
    diaSemana = (ancla.getDay() + 6) % 7
  }
  Object.assign(nf, {
    nombre: f.nombre, tipo: f.tipo, monto: f.monto, dia: f.dia,
    dia_semana: diaSemana,
    frecuencia: f.frecuencia, categoria_id: f.categoria_id ?? '', cuenta_id: f.cuenta_id ?? ''
  })
  showForm.value = true
}
function cerrarFormFijo() {
  showForm.value = false; editando.value = null
  Object.assign(nf, {
    nombre: '', tipo: 'gasto', monto: null, dia: 1, dia_semana: null, frecuencia: 'mensual',
    categoria_id: '', cuenta_id: ''
  })
}
async function toggleFijo(f: Fijo) {
  await api.patch(`/recurrentes/${f.id}/toggle`); await cargar()
}
async function eliminarFijo(id: string) {
  if (!(await confirmar({ titulo: '¿Eliminar este fijo?', mensaje: 'Dejará de contar en tus fijos de cada mes.', ok: 'Eliminar', peligro: true }))) return
  await api.delete(`/recurrentes/${id}`); await cargar(); toast.mostrar('Fijo eliminado')
}
async function cargar() {
  error.value = ''
  const [c, r, cu] = await Promise.all([
    api.get('/categorias', { params: { solo_activas: false } }),
    api.get('/recurrentes').catch(() => ({ data: { items: [], resumen: null } })),
    api.get('/cuentas').catch(() => ({ data: [] }))
  ])
  cats.value = c.data
  fijos.value = r.data.items ?? []
  resumenFijos.value = r.data.resumen ?? null
  cuentas.value = cu.data
}
onMounted(cargar)
</script>

<style>
/* .chip vive en tokens.css */
.sub{font-size:13px;color:var(--ink-soft)}
.etiqueta{font-size:13px;font-weight:700;color:var(--ink-soft)}
.link{background:none;border:0;color:var(--ink-soft)}
.btn-new{background:var(--mint);color:var(--navy);border:0;border-radius:12px;padding:10px 14px;font-weight:800;white-space:nowrap}
.pill-fr{display:inline-block;padding:1px 8px;border-radius:8px;font-size:11.5px;font-weight:700;background:var(--mint-soft);color:var(--mint-text)}
</style>
