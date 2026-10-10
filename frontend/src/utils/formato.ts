/** Formato es-CO de numeros y dinero. Fuente unica: reemplaza el `fmt` duplicado
 *  en 7 vistas (que ademas usaba `$` fijo, asi que elegir EUR renderizaba "$"). */

const LOCALE = 'es-CO'

export const SIMBOLO: Record<string, string> = {
  COP: '$', USD: '$', MXN: '$', EUR: '€'
}
export const DECIMALES: Record<string, number> = {
  COP: 0, USD: 0, MXN: 0, EUR: 2
}

export function simbolo(moneda: string | null | undefined): string {
  return SIMBOLO[(moneda ?? 'COP').toUpperCase()] ?? '$'
}

/** 1800000 -> '1.800.000' */
export function numero(v: unknown, decimales = 0): string {
  const n = Number(v ?? 0)
  if (!Number.isFinite(n)) return '0'
  return n.toLocaleString(LOCALE, {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales
  })
}

/** 1800000 con moneda COP -> '$1.800.000'. Sin moneda usa '$' (retrocompatible). */
export function dinero(v: unknown, moneda?: string | null, decimales?: number): string {
  const m = (moneda ?? 'COP').toUpperCase()
  const d = decimales ?? DECIMALES[m] ?? 0
  return `${simbolo(m)}${numero(v, d)}`
}

/** Compacto para tarjetas donde no cabe el numero completo: 1.8M, 250k */
export function dineroCorto(v: unknown, moneda?: string | null): string {
  const m = (moneda ?? 'COP').toUpperCase()
  const n = Number(v ?? 0)
  const abs = Math.abs(n)
  const signo = n < 0 ? '-' : ''
  if (abs >= 1_000_000_000) return `${signo}${simbolo(m)}${numero(abs / 1_000_000_000, 1)}MM`
  if (abs >= 1_000_000) return `${signo}${simbolo(m)}${numero(abs / 1_000_000, 1)}M`
  if (abs >= 10_000) return `${signo}${simbolo(m)}${numero(abs / 1000, 0)}k`
  return `${signo}${simbolo(m)}${numero(abs, DECIMALES[m] ?? 0)}`
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
