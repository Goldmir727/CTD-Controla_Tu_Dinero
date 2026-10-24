import { computed, ref } from 'vue'

/**
 * Un solo hueco para banners transitorios.
 *
 * Antes cada banner se posicionaba por su cuenta (cookies a bottom:12, update a
 * 84, install a 168) y podían aparecer dos a la vez encima de la barra de
 * navegación. Aquí se decide cuál se ve, en orden de prioridad: primero lo
 * legal/consentimiento, después cookies, actualización e instalación.
 *
 * El consentimiento legal no usa este hueco porque es un modal bloqueante; aun
 * así se deja en la lista para que, si algún día vuelve a ser banner, tenga la
 * prioridad más alta.
 */
type SlotId = 'legal' | 'cookies' | 'update' | 'install'

const ORDEN: SlotId[] = ['legal', 'cookies', 'update', 'install']
const pedidos = ref<Record<SlotId, boolean>>({
  legal: false,
  cookies: false,
  update: false,
  install: false
})

export function useBannerSlot(id: SlotId) {
  const visible = computed(() => ORDEN.find((k) => pedidos.value[k]) === id)

  /** Pide (o libera) el hueco. Es idempotente para no disparar renders de más. */
  function pedir(activo: boolean) {
    if (pedidos.value[id] === activo) return
    pedidos.value = { ...pedidos.value, [id]: activo }
  }

  return { visible, pedir }
}
