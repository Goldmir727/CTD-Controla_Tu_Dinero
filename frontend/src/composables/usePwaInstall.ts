import { computed, ref } from 'vue'

/** Instalación PWA compartida: banner automático + botón manual en Ajustes. */
const deferred = ref<{ prompt: () => void } | null>(
  (window as unknown as { __ctdInstallEvt?: { prompt: () => void } }).__ctdInstallEvt ?? null
)
const dismissed = ref(localStorage.getItem('ctd-install-no') === '1')

const esIOS = /iphone|ipad|ipod/i.test(navigator.userAgent)
/** Ya instalada (standalone) o sin soporte: no ofrecer. */
const yaInstalada = ref(
  matchMedia('(display-mode: standalone)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
)

window.addEventListener('appinstalled', () => {
  yaInstalada.value = true
})

export type Chequeo = { ok: boolean | null; label: string; detalle: string }

export function usePwaInstall() {
  const disponible = computed(() => !!deferred.value && !yaInstalada.value)
  const mostrarBanner = computed(() => disponible.value && !dismissed.value)

  function capturar(e: Event) {
    e.preventDefault()
    deferred.value = e as unknown as { prompt: () => void }
  }

  /** Compat: si el evento llegó antes que Vue, rescatarlo del stash global. */
  function rescatar() {
    const stash = (window as unknown as { __ctdInstallEvt?: { prompt: () => void } }).__ctdInstallEvt
    if (stash && !deferred.value) deferred.value = stash
  }

  async function instalar(): Promise<boolean> {
    rescatar()
    if (!deferred.value) return false
    deferred.value.prompt()
    deferred.value = null
    dismissed.value = true
    localStorage.setItem('ctd-install-no', '1')
    return true
  }

  function descartar() {
    dismissed.value = true
    localStorage.setItem('ctd-install-no', '1')
  }

  function reactivar() {
    // Permite volver a mostrar el banner (Ajustes) si el navegador lo permite
    dismissed.value = false
    localStorage.removeItem('ctd-install-no')
  }

  /** Revisa en vivo cada criterio que Chrome exige para instalar. */
  async function diagnosticar(): Promise<Chequeo[]> {
    const host = location.hostname
    const enLocal = host === 'localhost' || host === '127.0.0.1'
    const seguro = location.protocol === 'https:' || enLocal
    const haySW = 'serviceWorker' in navigator
    let swReg = false
    let swControl = false
    let swMotivo = ''
    try {
      swReg = !!(await navigator.serviceWorker?.getRegistration())
      swControl = !!navigator.serviceWorker?.controller
      if (!swReg && haySW) {
        // Intento explícito para capturar el motivo real (cert, red, etc.)
        try {
          await navigator.serviceWorker.register(`${import.meta.env.BASE_URL}sw.js`)
          swReg = true
          swMotivo = 'Registrado ahora: recarga la página.'
        } catch (e: unknown) {
          swMotivo = e instanceof Error ? e.message : 'Registro rechazado.'
        }
      }
    } catch { /* sin SW */ }
    let mani = false
    let maniDet = 'No se encontró el manifest.'
    try {
      const link = document.querySelector<HTMLLinkElement>("link[rel='manifest']")
      if (link) {
        const r = await fetch(link.href)
        const j = await r.json()
        mani = !!j.icons?.length && !!j.start_url
        maniDet = mani ? `${j.short_name || j.name} · ${j.icons.length} iconos.` : 'Manifest incompleto.'
      }
    } catch {
      maniDet = 'No se pudo leer el manifest.'
    }
    rescatar()
    const detReg = !haySW
      ? 'Este navegador no soporta service workers.'
      : swMotivo || (swReg ? 'Registrado.' : 'Recarga la página 2 veces.')
    return [
      { ok: seguro, label: 'Conexión segura (HTTPS)', detalle: seguro ? location.origin : 'Abre por https, no http.' },
      { ok: haySW && swReg, label: 'Service worker registrado', detalle: detReg },
      { ok: haySW && swControl, label: 'SW controlando la página', detalle: swControl ? 'Activo.' : 'Si ya registraste arriba, cierra y reabre la pestaña.' },
      { ok: mani, label: 'Manifest válido', detalle: maniDet },
      {
        ok: deferred.value ? true : null,
        label: 'El navegador ofrece instalar',
        detalle: deferred.value
          ? 'Evento capturado: usa el botón Instalar.'
          : 'Aún no llega: quita el acceso directo viejo, recarga 2 veces y espera unos segundos.'
      }
    ]
  }

  return { disponible, mostrarBanner, esIOS, yaInstalada, capturar, rescatar, instalar, descartar, reactivar, diagnosticar }
}
