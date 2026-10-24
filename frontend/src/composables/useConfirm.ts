import { reactive } from 'vue'

/**
 * Confirmaciones dentro de la app, en lugar de `window.confirm()`.
 *
 * El `confirm` del navegador bloquea el hilo, ignora el tema (aparece un cuadro
 * gris del sistema encima de una app oscura), no se puede leer bien en móvil y
 * no distingue una acción destructiva de una normal. Aquí es una sola promesa:
 *
 *   if (!(await confirmar({ titulo: '¿Eliminar?', peligro: true }))) return
 *
 * El diálogo se pinta una sola vez en App.vue.
 */
export type OpcionesConfirm = {
  titulo: string
  mensaje?: string
  ok?: string
  cancelar?: string
  /** Pinta la acción en rojo: borrar, salir, descartar. */
  peligro?: boolean
}

const DEFECTOS = { mensaje: '', ok: 'Aceptar', cancelar: 'Cancelar', peligro: false }

export const estadoConfirm = reactive({ titulo: '', abierto: false, ...DEFECTOS })

let resolver: ((valor: boolean) => void) | null = null

export function confirmar(opciones: OpcionesConfirm): Promise<boolean> {
  // Si ya había uno esperando, se cierra como cancelado: si no, su promesa
  // quedaría colgada para siempre y la acción se ejecutaría tarde o nunca.
  resolver?.(false)
  Object.assign(estadoConfirm, DEFECTOS, opciones, { abierto: true })
  return new Promise<boolean>((res) => {
    resolver = res
  })
}

export function responderConfirm(valor: boolean) {
  estadoConfirm.abierto = false
  const r = resolver
  resolver = null
  r?.(valor)
}
