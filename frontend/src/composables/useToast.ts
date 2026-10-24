import { ref } from 'vue'

/**
 * Registro único de avisos transitorios.
 *
 * Antes cada vista avisaba a su manera (un `msg` inline aquí, un `alert` del
 * navegador allá) y las acciones destructivas no decían nada al terminar: el
 * usuario borraba un movimiento y no tenía forma de saber si se había hecho.
 * Aquí todos los avisos pasan por el mismo sitio, con el mismo tono y la misma
 * duración.
 */
export type TipoToast = 'ok' | 'error' | 'info'
export type Toast = { id: number; texto: string; tipo: TipoToast }

const lista = ref<Toast[]>([])
let seq = 0

/** Un error se lee, una confirmación se ve de reojo: no duran lo mismo. */
const DURACION: Record<TipoToast, number> = { ok: 3200, info: 3200, error: 5000 }
/** Máximo en pantalla: encolar cinco avisos tapa media pantalla en un móvil. */
const MAXIMO = 3

function quitar(id: number) {
  lista.value = lista.value.filter((t) => t.id !== id)
}

export function useToast() {
  function mostrar(texto: string, tipo: TipoToast = 'ok', ms = DURACION[tipo]) {
    const id = ++seq
    lista.value = [...lista.value, { id, texto, tipo }].slice(-MAXIMO)
    if (ms > 0) setTimeout(() => quitar(id), ms)
    return id
  }

  return { lista, mostrar, quitar }
}
