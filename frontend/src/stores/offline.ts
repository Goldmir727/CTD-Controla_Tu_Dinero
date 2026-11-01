import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  isOnline,
  obtenerEstadoCola,
  procesarColaSincronizacion,
} from '../services/repository'

/**
 * Estado de conexión y de la cola de cambios sin enviar.
 *
 * Lo que el usuario necesita saber es doble: si está sin red y cuándo su trabajo
 * ya llegó al servidor. Un contador de "pendientes" que se queda en cero no sirve
 * para lo segundo, así que se refresca al arrancar, después de cada sincronización
 * y cada vez que se registra algo.
 */
export const useOffline = defineStore('offline', () => {
  const conectado = ref(isOnline())
  const sincronizando = ref(false)
  const pendientes = ref(0)
  const ultimoError = ref('')
  let iniciado = false

  function actualizarConexion() {
    conectado.value = isOnline()
  }

  async function refreshPendientes() {
    try {
      pendientes.value = await obtenerEstadoCola()
    } catch {
      pendientes.value = 0
    }
  }

  async function sincronizar() {
    if (sincronizando.value) return
    if (!isOnline()) return
    sincronizando.value = true
    ultimoError.value = ''
    try {
      const res = await procesarColaSincronizacion()
      if (res.fail > 0) {
        ultimoError.value = 'Algunos cambios no se pudieron enviar. Se reintentará al volver la red.'
      }
      return res
    } catch {
      ultimoError.value = 'No se pudo sincronizar. Se reintentará al volver la red.'
    } finally {
      sincronizando.value = false
      await refreshPendientes()
    }
  }

  /** Se llama una sola vez al arrancar la app. */
  function iniciar() {
    if (iniciado || typeof window === 'undefined') return
    iniciado = true
    actualizarConexion()
    void refreshPendientes()
    window.addEventListener('online', () => {
      conectado.value = true
      void sincronizar()
    })
    window.addEventListener('offline', () => {
      conectado.value = false
    })
  }

  return {
    conectado: computed(() => conectado.value),
    sincronizando: computed(() => sincronizando.value),
    pendientes: computed(() => pendientes.value),
    hayPendientes: computed(() => pendientes.value > 0),
    ultimoError: computed(() => ultimoError.value),
    actualizarConexion,
    sincronizar,
    refreshPendientes,
    iniciar,
  }
})
