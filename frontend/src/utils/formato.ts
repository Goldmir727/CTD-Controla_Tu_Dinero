/** Formato de numeros y dinero segun el PAIS del usuario. Fuente unica: reemplaza
 *  el `fmt` duplicado en 7 vistas (que ademas usaba `$` fijo, asi que elegir EUR
 *  renderizaba "$").
 *
 *  Antes el locale estaba en es-CO fijo. Con eso un usuario de Estados Unidos veia
 *  "$1.234.567" en vez de "$1,234,567": el separador de miles no cambia por el
 *  codigo de moneda sino por el pais. Y COP, USD y MXN comparten el simbolo "$",
 *  asi que cambiar de moneda no cambiaba NADA visible.
 *
 *  El locale no se pasa por parametro a cada llamada porque eso obligaria a
 *  tocar todas las vistas. Se configura una vez al cargar la sesion y se usa
 *  como estado del modulo. */

/**
 * El simbolo y los decimales salen SIEMPRE de la MONEDA. El pais solo cambia
 * los separadores.
 *
 * Este es el bug que ya se comio una vez: al meter el pais, el simbolo paso a
 * salir de ahi y un usuario con 1.800.000 pesos (unos 450 dolares) que cambiaba
 * el pais a Estados Unidos veia "$1,800,000.00". El numero no convertia, se le
 * cambiaba la etiqueta, y la app le decia que tenia 4000 veces mas plata.
 *
 * Cambiar de pais no convierte ni reetiqueta dinero. Convertir de verdad es otra
 * operacion y esta app no la hace: no tiene tipo de cambio ni puede inventarse uno.
 */
export type Formato = { locale: string; pais: string }

const POR_DEFECTO: Formato = { locale: 'es-CO', pais: 'CO' }

let actual: Formato = { ...POR_DEFECTO }

export function configurarFormato(pais?: string | null, _moneda?: string | null) {
  if (!pais) { actual = { ...POR_DEFECTO }; return actual }
  const c = pais.toUpperCase()
  actual = { pais: c, locale: LOCALE_POR_PAIS[c] ?? 'es-CO' }
  return actual
}

export function formatoActual(): Formato { return actual }

/** Se usa antes de tener sesion (landing, registro) para no mezclar formatos. */
export function usarPorDefecto() { actual = { ...POR_DEFECTO } }

export const SIMBOLO: Record<string, string> = {
  COP: '$', USD: '$', MXN: '$', EUR: '€',
  ARS: '$', CLP: '$', PEN: 'S/', BRL: 'R$',
}
export const DECIMALES: Record<string, number> = {
  COP: 0, USD: 2, MXN: 2, EUR: 2,
  ARS: 2, CLP: 0, PEN: 2, BRL: 2,
}
/** Solo el PAIS cambia el separador de miles. */
export const LOCALE_POR_PAIS: Record<string, string> = {
  CO: 'es-CO', MX: 'es-MX', US: 'en-US', AR: 'es-AR', CL: 'es-CL',
  EC: 'es-EC', PE: 'es-PE', ES: 'es-ES', BR: 'pt-BR',
}

/** El simbolo es de la MONEDA. Cambiar de pais no lo cambia. */
export function simbolo(moneda: string | null | undefined): string {
  return SIMBOLO[(moneda ?? 'COP').toUpperCase()] ?? '$'
}

export function locale(): string { return actual.locale }

function decimalesDe(moneda: string | null | undefined): number {
  return DECIMALES[(moneda ?? 'COP').toUpperCase()] ?? 0
}

/**
 * 1800000 -> '1.800.000' en Colombia, '1,800,000' en Estados Unidos.
 * El segundo parametro son DECIMALES (no la moneda): asi lo usan las 12 llamadas
 * que ya existen en las vistas.
 */
export function numero(v: unknown, decimales = 0): string {
  const n = Number(v ?? 0)
  if (!Number.isFinite(n)) return '0'
  return n.toLocaleString(actual.locale, {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales
  })
}

/**
 * 1800000 en pesos -> '$1.800.000' en Colombia, '$1,800,000' en Estados Unidos.
 *
 * El numero conserva SU VALOR y solo cambia como se escribe. El simbolo y los
 * decimales vienen de la moneda, nunca del pais.
 */
export function dinero(v: unknown, moneda?: string | null, decimales?: number): string {
  const d = decimales ?? decimalesDe(moneda)
  return `${simbolo(moneda)}${numero(v, d)}`
}

/** Compacto para tarjetas donde no cabe el numero completo: 1.8M, 250k */
export function dineroCorto(v: unknown, moneda?: string | null): string {
  const n = Number(v ?? 0)
  const abs = Math.abs(n)
  const signo = n < 0 ? '-' : ''
  if (abs >= 1_000_000_000) return `${signo}${simbolo(moneda)}${numero(abs / 1_000_000_000, 1)}MM`
  if (abs >= 1_000_000) return `${signo}${simbolo(moneda)}${numero(abs / 1_000_000, 1)}M`
  if (abs >= 10_000) return `${signo}${simbolo(moneda)}${numero(abs / 1000, 0)}k`
  return `${signo}${simbolo(moneda)}${numero(abs, decimalesDe(moneda))}`
}

/**
 * Codigo ISO de la moneda: "COP", "USD", "EUR"...
 *
 * Por que hace falta: el simbolo no alcanza. COP, USD, MXN, ARS y CLP comparten
 * "$", y ademas cambiar de pais reescribe 1.800.000 como "$1,800,000", que se
 * lee como un millón ochocientos mil DOLARES aunque sean pesos. El codigo es lo
 * unico que no se puede confundir.
 *
 * No se pone en cada numero: seria ruido. Va en las cifras grandes, que son las
 * que el usuario lee de verdad.
 */
export function codigo(moneda: string | null | undefined): string {
  return (moneda ?? 'COP').toUpperCase()
}

/** Dinero con su unidad explicita, para las cifras que el usuario mira de frente. */
export function dineroConUnidad(v: unknown, moneda?: string | null, decimales?: number): string {
  return `${dinero(v, moneda, decimales)} ${codigo(moneda)}`
}

export function porcentaje(v: unknown, decimales = 1): string {
  return `${numero(v, decimales)}%`
}

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
  'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

/** '2026-10' -> 'Octubre 2026' (para titulos). */
export function mesEs(ym: string): string {
  const [a, m] = (ym ?? '').split('-')
  const i = Number(m) - 1
  if (!a || Number.isNaN(i) || !MESES[i]) return ym ?? ''
  return `${MESES[i][0].toUpperCase()}${MESES[i].slice(1)} ${a}`
}

/** '2026-10-08' -> '8 oct' (para grupos de lista). */
export function fechaCorta(iso: string): string {
  const d = (iso ?? '').slice(0, 10).split('-')
  if (d.length < 3) return iso ?? ''
  const i = Number(d[1]) - 1
  return `${Number(d[2])} ${MESES[i]?.slice(0, 3) ?? ''}`
}

/** Con signo, para saldos: +1.200.000 / -300.000 con el simbolo de la moneda. */
export function firmado(v: unknown, moneda?: string | null, decimales?: number): string {
  const m = (moneda ?? 'COP').toUpperCase()
  const d = decimales ?? DECIMALES[m] ?? 0
  const n = Number(v ?? 0)
  return `${n > 0 ? '+' : n < 0 ? '-' : ''}${simbolo(m)}${numero(Math.abs(n), d)}`
}
