<script setup lang="ts">
/** Selector de perfil: Personal o Negocio.
 *
 *  Vive en el header porque el perfil decide qué cifras se ven en TODA la app:
 *  cambiarlo aquí cambia Inicio, Movimientos, Plan, Datos, Asesor y la captura.
 *
 *  No se guarda el perfil activo como "por defecto del usuario" en cada request:
 *  va en localStorage y viaja como header, para que el usuario pueda alternar sin
 *  que el backend tenga que mutar nada. */
import { computed, onMounted, ref } from 'vue'
import api from '../services/api'

type Perfil = {
  id: string
  nombre: string
  tipo: 'personal' | 'negocio'
  principal: boolean
  notificar_mezcla: boolean
  activo: boolean
}

const emit = defineEmits<{ (e: 'cambio'): void }>()

const perfiles = ref<Perfil[]>([])
const abierto = ref(false)
const cargando = ref(false)
const error = ref('')
const nuevo = ref('')

const CLAVE = 'ctd-perfil'
const activo = computed(() => perfiles.value.find((p) => p.activo) ?? null)

async function cargar() {
  if (!localStorage.getItem('access_token')) return
  try {
    const { data } = await api.get('/perfiles')
    // El backend dice cuál está activo; si guardamos uno que ya no existe, se
    // descarta y mandamos el principal.
    const guardado = localStorage.getItem(CLAVE)
    const elegido = data.items.find((p: Perfil) => p.id === guardado)
    const actual = elegido ?? data.items.find((p: Perfil) => p.principal) ?? data.items[0]
    if (actual && !elegido) localStorage.setItem(CLAVE, actual.id)
    perfiles.value = data.items
  } catch { /* sin perfiles: la app sigue igual */ }
}

async function elegir(p: Perfil) {
  localStorage.setItem(CLAVE, p.id)
  perfiles.value = perfiles.value.map((x) => ({ ...x, activo: x.id === p.id }))
  abierto.value = false
  emit('cambio')
}

async function crear() {
  const nombre = nuevo.value.trim()
  if (!nombre || cargando.value) return
  cargando.value = true
  error.value = ''
  try {
    const { data } = await api.post('/perfiles', { nombre, tipo: 'negocio' })
    await cargar()
    localStorage.setItem(CLAVE, data.id)
    perfiles.value = perfiles.value.map((x) => ({ ...x, activo: x.id === data.id }))
    nuevo.value = ''
    emit('cambio')
  } catch (e: unknown) {
    error.value = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
      ?? 'No pude crear el perfil.'
  } finally {
    cargando.value = false
  }
}

onMounted(cargar)
defineExpose({ cargar })
</script>

<template>
  <div v-if="perfiles.length" class="perfil-wrap">
    <button class="perfil-btn" :class="activo?.tipo" @click="abierto = !abierto"
            :aria-expanded="abierto" :aria-haspopup="perfiles.length > 1 ? 'menu' : undefined"
            :aria-label="perfiles.length > 1 ? 'Cambiar entre Personal y Negocio' : 'Tu perfil'"
            :title="perfiles.length > 1 ? 'Cambiar entre Personal y Negocio' : 'Tu perfil'">
      <i class="bi" :class="activo?.tipo === 'negocio' ? 'bi-shop' : 'bi-person'"></i>
      <span>{{ activo?.nombre ?? 'Perfil' }}</span>
      <i v-if="perfiles.length > 1" class="bi bi-chevron-down flecha"></i>
    </button>

    <div v-if="abierto" class="perfil-menu" @click.stop>
      <p class="sub titulo">¿Estás viendo las finanzas de…</p>
      <button v-for="p in perfiles" :key="p.id" class="perfil-item"
              :class="{ on: p.activo }" @click="elegir(p)">
        <i class="bi" :class="p.tipo === 'negocio' ? 'bi-shop' : 'bi-person'"></i>
        <span>{{ p.nombre }}</span>
        <small>{{ p.tipo === 'negocio' ? 'Negocio' : 'Personal' }}</small>
        <i v-if="p.activo" class="bi bi-check-lg ok"></i>
      </button>

      <hr class="divider" />
      <p class="sub titulo">Agrega tu negocio</p>
      <div class="fila">
        <input v-model="nuevo" class="input" placeholder="Nombre: Tienda, Taller…"
               maxlength="60" @keyup.enter="crear" />
        <button class="btn-mint chiquito" :disabled="cargando || !nuevo.trim()"
                @click="crear">
          <span v-if="cargando" class="spinner"></span>
          <i v-else class="bi bi-plus-lg"></i>
        </button>
      </div>
      <p v-if="error" class="alert mini">{{ error }}</p>
      <p v-else class="sub nota">
        Las cuentas, categorías, presupuestos y metas de cada perfil se llevan por
        separado. CTD te avisa si se te escapa plata del negocio a gastos tuyos.
      </p>
    </div>
    <div v-if="abierto" class="perfil-fondo" @click="abierto = false"></div>
  </div>
</template>

<style scoped>
.perfil-wrap { position: relative; }
.perfil-btn {
  display: flex; align-items: center; gap: 5px;
  border: 1px solid var(--line); background: var(--surface);
  border-radius: 999px; padding: 6px 11px; font: 600 12px var(--font);
  color: var(--ink); cursor: pointer; max-width: 132px; min-height: 44px;
}
.perfil-btn span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.perfil-btn.negocio { border-color: var(--mint-dark); color: var(--mint-text); background: var(--mint-tint); }
.perfil-btn:focus-visible { outline: none; box-shadow: 0 0 0 3px rgba(0, 255, 171, 0.25); }
.flecha { font-size: 10px; opacity: .6; }

.perfil-fondo { position: fixed; inset: 0; z-index: 45; }
.perfil-menu {
  position: absolute; top: calc(100% + 8px); right: 0; z-index: 46;
  width: 264px; padding: 12px;
  background: var(--surface); border: 1px solid var(--line);
  border-radius: 16px; box-shadow: var(--shadow);
}
.titulo { margin: 2px 0 8px; font-weight: 600; }
.perfil-item {
  display: flex; align-items: center; gap: 8px; width: 100%; min-height: 44px;
  padding: 9px 8px; border: 0; border-radius: 10px;
  background: none; color: var(--ink); font: 500 14px var(--font);
  text-align: left; cursor: pointer;
}
.perfil-item:hover { background: var(--bg); }
.perfil-item span { flex: 1; }
.perfil-item small { color: var(--ink-soft); font-size: 11px; }
.perfil-item .ok { color: var(--mint-text); }
.perfil-item.on { background: var(--mint-soft); }

.fila { display: flex; gap: 6px; }
.fila .input { flex: 1; min-width: 0; padding: 8px 10px; font-size: 13px; }
.chiquito { width: 38px; padding: 8px 0; }
.nota { margin-top: 8px; font-size: 11px; }
.mini { margin: 6px 0 0; font-size: 12px; padding: 6px 8px; }
</style>