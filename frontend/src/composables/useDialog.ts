import { nextTick, onBeforeUnmount, watch, type Ref } from 'vue'

const FOCUSABLES =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

type Opciones = {
  /** Escape cierra. Se apaga en diálogos legales que no se pueden descartar. */
  esc?: boolean
}

/**
 * Diálogo accesible mínimo: atrapa el foco dentro, cierra con Escape, bloquea
 * el scroll de fondo y devuelve el foco al elemento que lo abrió.
 *
 * Sin esto, una hoja abierta dejaba el foco detrás (se podía tabular a la
 * página de abajo) y el lector de pantalla seguía leyendo la pantalla de fondo.
 */
/**
 * Diálogos abiertos, de abajo hacia arriba. Solo el último responde a Escape y
 * atrapa el Tab: sin esto, un confirm encima de una hoja cerraba las dos cosas a
 * la vez con un solo Escape.
 */
const pila: symbol[] = []
/** Cuántos diálogos piden bloqueo de scroll (no basta con encender/apagar). */
let bloqueos = 0

export function useDialog(
  abierto: Ref<boolean>,
  contenedor: Ref<HTMLElement | null>,
  alCerrar: () => void,
  opciones: Opciones = {}
) {
  let previo: HTMLElement | null = null
  let activo = false
  const yo = Symbol('dialogo')

  function focusables(): HTMLElement[] {
    const raiz = contenedor.value
    if (!raiz) return []
    return Array.from(raiz.querySelectorAll<HTMLElement>(FOCUSABLES)).filter(
      (el) => el.offsetParent !== null || el === document.activeElement
    )
  }

  function alTeclado(e: KeyboardEvent) {
    if (pila[pila.length - 1] !== yo) return
    if (e.key === 'Escape' && opciones.esc !== false) {
      e.preventDefault()
      alCerrar()
      return
    }
    if (e.key !== 'Tab') return
    const els = focusables()
    if (!els.length) return
    const primero = els[0]
    const ultimo = els[els.length - 1]
    if (e.shiftKey && document.activeElement === primero) {
      e.preventDefault()
      ultimo.focus()
    } else if (!e.shiftKey && document.activeElement === ultimo) {
      e.preventDefault()
      primero.focus()
    }
  }

  watch(
    abierto,
    async (valor) => {
      if (valor) {
        activo = true
        pila.push(yo)
        bloqueos += 1
        previo = document.activeElement as HTMLElement | null
        document.addEventListener('keydown', alTeclado)
        document.body.style.overflow = 'hidden'
        await nextTick()
        const raiz = contenedor.value
        const inicial =
          raiz?.querySelector<HTMLElement>('[data-autofocus]') ?? focusables()[0]
        inicial?.focus()
      } else {
        if (!activo) return
        activo = false
        const i = pila.indexOf(yo)
        if (i >= 0) pila.splice(i, 1)
        bloqueos = Math.max(0, bloqueos - 1)
        document.removeEventListener('keydown', alTeclado)
        if (!bloqueos) document.body.style.overflow = ''
        previo?.focus?.()
        previo = null
      }
    },
    { immediate: true }
  )

  onBeforeUnmount(() => {
    document.removeEventListener('keydown', alTeclado)
    const i = pila.indexOf(yo)
    if (i >= 0) pila.splice(i, 1)
    if (activo) {
      activo = false
      bloqueos = Math.max(0, bloqueos - 1)
      if (!bloqueos) document.body.style.overflow = ''
    }
  })
}
