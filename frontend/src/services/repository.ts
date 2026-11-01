import api from './api'
import {
  encolarSincronizacion,
  obtenerColaSincronizacion,
  removerDeCola,
  actualizarReintentos,
  guardarMovimientoLocal,
  obtenerMovimientosLocales,
  eliminarMovimientoLocal,
  guardarRecurrenteLocal,
  obtenerRecurrentesLocales,
  eliminarRecurrenteLocal,
  guardarPerfilLocal,
  obtenerPerfilesLocales,
  guardarCategoriaLocal,
  obtenerCategoriasLocales,
  reemplazarCuentasLocales,
  obtenerCuentasLocales,
  reemplazarMetodosLocales,
  obtenerMetodosLocales,
  type MovimientoLocal,
  type RecurrenteLocal,
} from './db'

type Movimiento = {  id: string
  tipo: 'ingreso' | 'gasto'
  monto: number
  descripcion: string
  categoria: string | null
  cuenta: string | null
  fecha: string
  perfil_id?: string
  cuenta_id?: string | null
  categoria_id?: string | null
  metodo_id?: string | null
  recurrente_id?: string | null
  idempotency_key?: string | null
  created_at?: string
}

export type ResumenRecurrentes = {
  cantidad: number
  ingresos_fijos_mes: number
  gastos_fijos_mes: number
  neto_fijo_mes: number
  ratio_fijo: number | null
}
export type Recurrente = {
  id: string
  nombre: string
  tipo: 'ingreso' | 'gasto'
  monto: number
  cuenta_id: string | null
  categoria_id: string | null
  dia: number
  frecuencia: 'mensual' | 'quincenal' | 'semanal'
  dia_semana: number | null
  confirmado: boolean
  activo: boolean
  nota: string | null
  perfil_id?: string
  created_at?: string
  monto_mes?: number
  etiqueta?: string | null
  proxima?: string | null
  categoria?: string | null
}

type Perfil = {
  id: string
  user_id: string
  nombre: string
  tipo: string
  principal: boolean
  notificar_mezcla: boolean
  created_at: string
}

/** Lo que se manda al crear: mismo shape que el backend, sin id ni created_at. */
export type NuevoMovimiento = {
  tipo: 'ingreso' | 'gasto'
  monto: number
  fecha: string
  descripcion?: string
  cuenta_id: string
  categoria_id?: string | null
  metodo_id?: string | null
  recurrente_id?: string | null
  perfil_id?: string
  idempotency_key?: string | null
}

let online = typeof navigator !== 'undefined' ? navigator.onLine : true

window.addEventListener('online', () => { online = true })
window.addEventListener('offline', () => { online = false })

export function isOnline(): boolean {
  return online
}

/** Perfil activo segun el header que manda api.ts. Se guarda junto a cada
 *  movimiento local: sin eso el indice por perfil de IndexedDB no encuentra
 *  nada y la lista aparece vacia justo cuando no hay red. */
function perfilActivo(): string {
  if (typeof localStorage === 'undefined') return ''
  return localStorage.getItem('ctd-perfil') ?? ''
}

function aLocal(m: Movimiento): MovimientoLocal {
  return {
    id: m.id, perfil_id: m.perfil_id || perfilActivo(), tipo: m.tipo, monto: m.monto,
    descripcion: m.descripcion ?? '', categoria: m.categoria ?? null, cuenta: m.cuenta ?? null,
    fecha: m.fecha, cuenta_id: m.cuenta_id ?? null, categoria_id: m.categoria_id ?? null,
    metodo_id: m.metodo_id ?? null, recurrente_id: m.recurrente_id ?? null,
    idempotency_key: m.idempotency_key ?? null, created_at: m.created_at ?? '',
  }
}

/** ---------- Movimientos ---------- */

export async function listarMovimientos(perfilId?: string): Promise<Movimiento[]> {
  // Offline: devolver locales. Online: API primero, luego cachear en local.
  if (!online) {
    return obtenerMovimientosLocales(perfilId || undefined)
  }
  try {
    // El backend pagina: sin page_size explicito solo se cacheaban 20. Se pide
    // una pagina amplia para que el historial offline sea el que el usuario ve.
    const { data } = await api.get<Movimiento[] | { items: Movimiento[] }>('/movimientos', {
      params: { perfil_id: perfilId, page_size: 200 },
    })
    const lista = Array.isArray(data) ? data : data.items ?? []
    for (const m of lista) {
      await guardarMovimientoLocal(aLocal({ ...m, perfil_id: m.perfil_id || perfilId }))
    }
    return lista
  } catch {
    return obtenerMovimientosLocales(perfilId || undefined)
  }
}

export async function crearMovimiento(m: NuevoMovimiento): Promise<Movimiento> {
  const id = crypto.randomUUID()
  // La misma clave viaja al servidor si la red se cae a mitad de camino: el
  // backend reutiliza el movimiento en vez de duplicarlo al reintentar.
  const clave = m.idempotency_key || id
  const local: Movimiento = {
    ...m,
    id,
    descripcion: m.descripcion ?? '',
    categoria: null,
    cuenta: null,
    perfil_id: m.perfil_id || perfilActivo(),
    idempotency_key: clave,
    created_at: new Date().toISOString(),
  }

  // Siempre guardar localmente primero
  await guardarMovimientoLocal(aLocal(local))

  if (!online) {
    await encolarSincronizacion({
      type: 'movimiento',
      payload: local,
      method: 'POST',
      endpoint: '/movimientos',
    })
    return local
  }

  try {
    const { data } = await api.post<Movimiento>('/movimientos', m, {
      headers: { 'Idempotency-Key': clave },
    })
    // El servidor manda el movimiento ya guardado (puede ser el mismo que se
    // reutilizo por idempotencia). Se reemplaza la copia local por esa.
    await eliminarMovimientoLocal(local.id)
    await guardarMovimientoLocal(aLocal({ ...data, idempotency_key: clave }))
    return data
  } catch (err) {
    // Si falla la API, mantener en local y encolar para reintento
    await encolarSincronizacion({
      type: 'movimiento',
      payload: local,
      method: 'POST',
      endpoint: '/movimientos',
    })
    throw err
  }
}

export async function eliminarMovimiento(id: string): Promise<void> {
  await eliminarMovimientoLocal(id)
  if (!online) {
    await encolarSincronizacion({
      type: 'eliminar_movimiento',
      payload: { id },
      method: 'DELETE',
      endpoint: `/movimientos/${id}`,
    })
    return
  }
  try {
    await api.delete(`/movimientos/${id}`)
  } catch {
    await encolarSincronizacion({
      type: 'eliminar_movimiento',
      payload: { id },
      method: 'DELETE',
      endpoint: `/movimientos/${id}`,
    })
    throw new Error('Movimiento eliminado localmente. Se sincronizara al recuperar conexion.')
  }
}

export async function editarMovimiento(id: string, cambios: Partial<Movimiento>): Promise<void> {
  // Aplicar cambios localmente inmediatamente (optimista)
  const locales = await obtenerMovimientosLocales()
  const local = locales.find((m) => m.id === id)
  if (local) {
    const actualizado: MovimientoLocal = { ...local, ...cambios }
    await guardarMovimientoLocal(actualizado)
  }

  if (!online) {
    await encolarSincronizacion({
      type: 'movimiento',
      payload: { ...local, ...cambios },
      method: 'PATCH',
      endpoint: `/movimientos/${id}`,
    })
    return
  }
  try {
    await api.patch(`/movimientos/${id}`, cambios)
  } catch {
    await encolarSincronizacion({
      type: 'movimiento',
      payload: { ...local, ...cambios },
      method: 'PATCH',
      endpoint: `/movimientos/${id}`,
    })
    throw new Error('Cambios guardados localmente. Se sincronizara al recuperar conexion.')
  }
}

/** ---------- Recurrentes (fijos) ---------- */

export async function listarRecurrentes(perfilId?: string): Promise<{ items: Recurrente[]; resumen: ResumenRecurrentes | null }> {
  if (!online) {
    return { items: await recurrentesDesdeLocal(perfilId), resumen: null }
  }
  try {
    const { data } = await api.get<Recurrente[] | { items: Recurrente[]; resumen?: ResumenRecurrentes | null }>('/recurrentes')
    // El backend responde {items, resumen}; otras versiones devolvian el array
    // suelto. Tratar el objeto como lista hacia que esta funcion entrara
    // siempre por el catch y la app viviera de datos viejos.
    const lista = Array.isArray(data) ? data : data.items ?? []
    const resumen = Array.isArray(data) ? null : data.resumen ?? null
    const filtrado = perfilId ? lista.filter((r) => r.perfil_id === perfilId || !r.perfil_id) : lista
    for (const r of filtrado) {
      await guardarRecurrenteLocal({
        id: r.id, nombre: r.nombre, tipo: r.tipo, monto: r.monto,
        cuenta_id: r.cuenta_id, categoria_id: r.categoria_id, dia: r.dia,
        frecuencia: r.frecuencia, dia_semana: r.dia_semana,
        confirmado: r.confirmado, activo: r.activo, nota: r.nota,
        perfil_id: r.perfil_id, created_at: r.created_at ?? '',
      })
    }
    return { items: filtrado, resumen }
  } catch {
    return { items: await recurrentesDesdeLocal(perfilId), resumen: null }
  }
}

async function recurrentesDesdeLocal(perfilId?: string): Promise<Recurrente[]> {
  const locales = await obtenerRecurrentesLocales(perfilId)
  return locales.map((r) => ({
    id: r.id, nombre: r.nombre, tipo: r.tipo, monto: r.monto,
    cuenta_id: r.cuenta_id, categoria_id: r.categoria_id, dia: r.dia,
    frecuencia: r.frecuencia, dia_semana: r.dia_semana,
    confirmado: r.confirmado, activo: r.activo, nota: r.nota,
    perfil_id: r.perfil_id, created_at: r.created_at,
    monto_mes: r.monto, etiqueta: undefined, proxima: undefined,
  }))
}

export async function crearRecurrente(r: Omit<Recurrente, 'id' | 'created_at'>): Promise<Recurrente> {
  const local: Recurrente = {
    ...r,
    id: crypto.randomUUID(),
    created_at: new Date().toISOString(),
  }
  await guardarRecurrenteLocal({
    id: local.id, nombre: local.nombre, tipo: local.tipo, monto: local.monto,
    cuenta_id: local.cuenta_id, categoria_id: local.categoria_id, dia: local.dia,
    frecuencia: local.frecuencia, dia_semana: local.dia_semana,
    confirmado: local.confirmado, activo: local.activo, nota: local.nota,
    perfil_id: local.perfil_id, created_at: String(local.created_at),
  })

  if (!online) {
    await encolarSincronizacion({
      type: 'recurrente',
      payload: local,
      method: 'POST',
      endpoint: '/recurrentes',
    })
    return local
  }

  try {
    const { data } = await api.post<Recurrente>('/recurrentes', r)
    if (data.id !== local.id) {
      await eliminarRecurrenteLocal(local.id)
      await guardarRecurrenteLocal({
        id: data.id, nombre: data.nombre, tipo: data.tipo, monto: data.monto,
        cuenta_id: data.cuenta_id, categoria_id: data.categoria_id, dia: data.dia,
        frecuencia: data.frecuencia, dia_semana: data.dia_semana,
        confirmado: data.confirmado, activo: data.activo, nota: data.nota,
        perfil_id: data.perfil_id, created_at: data.created_at ?? '',
      })
    }
    return data
  } catch (err) {
    await encolarSincronizacion({
      type: 'recurrente',
      payload: local,
      method: 'POST',
      endpoint: '/recurrentes',
    })
    throw err
  }
}

export async function eliminarRecurrente(id: string): Promise<void> {
  await eliminarRecurrenteLocal(id)
  if (!online) {
    await encolarSincronizacion({
      type: 'eliminar_recurrente',
      payload: { id },
      method: 'DELETE',
      endpoint: `/recurrentes/${id}`,
    })
    return
  }
  try {
    await api.delete(`/recurrentes/${id}`)
  } catch {
    await encolarSincronizacion({
      type: 'eliminar_recurrente',
      payload: { id },
      method: 'DELETE',
      endpoint: `/recurrentes/${id}`,
    })
    throw new Error('Recurrente eliminado localmente. Se sincronizara al recuperar conexion.')
  }
}

export async function editarRecurrente(id: string, cambios: Partial<Recurrente>): Promise<void> {
  const locales = await obtenerRecurrentesLocales()
  const local = locales.find((r) => r.id === id)
  if (local) {
    const actualizado: RecurrenteLocal = { ...local, ...cambios }
    await guardarRecurrenteLocal(actualizado)
  }

  if (!online) {
    await encolarSincronizacion({
      type: 'recurrente',
      payload: { ...local, ...cambios },
      method: 'PATCH',
      endpoint: `/recurrentes/${id}`,
    })
    return
  }
  try {
    await api.patch(`/recurrentes/${id}`, cambios)
  } catch {
    await encolarSincronizacion({
      type: 'recurrente',
      payload: { ...local, ...cambios },
      method: 'PATCH',
      endpoint: `/recurrentes/${id}`,
    })
    throw new Error('Cambios guardados localmente. Se sincronizara al recuperar conexion.')
  }
}

export async function toggleRecurrente(id: string): Promise<void> {
  if (!online) {
    // Toggle optimista localmente
    const locales = await obtenerRecurrentesLocales()
    const local = locales.find((r) => r.id === id)
    if (local) {
      await guardarRecurrenteLocal({ ...local, activo: !local.activo })
    }
    await encolarSincronizacion({
      type: 'recurrente',
      payload: { id },
      method: 'PATCH',
      endpoint: `/recurrentes/${id}/toggle`,
    })
    return
  }
  try {
    await api.patch(`/recurrentes/${id}/toggle`)
  } catch {
    const locales = await obtenerRecurrentesLocales()
    const local = locales.find((r) => r.id === id)
    if (local) {
      await guardarRecurrenteLocal({ ...local, activo: !local.activo })
    }
    await encolarSincronizacion({
      type: 'recurrente',
      payload: { id },
      method: 'PATCH',
      endpoint: `/recurrentes/${id}/toggle`,
    })
    throw new Error('Cambio guardado localmente. Se sincronizara al recuperar conexion.')
  }
}

export type CategoriaLocal = { id: string; nombre: string; tipo: string; activa?: boolean }

export async function listarCategorias(): Promise<CategoriaLocal[]> {
  if (!online) {
    return obtenerCategoriasLocales()
  }
  try {
    const { data } = await api.get<CategoriaLocal[]>('/categorias', { params: { solo_activas: false } })
    for (const c of data) await guardarCategoriaLocal({ id: c.id, nombre: c.nombre, tipo: c.tipo })
    return data
  } catch {
    return obtenerCategoriasLocales()
  }
}

export type Cuenta = { id: string; nombre: string; tipo?: string; saldo_actual?: number }

/** La cuenta es obligatoria al registrar: sin esta copia local el formulario
 *  queda sin opciones apenas se corta la red. */
export async function listarCuentas(): Promise<Cuenta[]> {
  if (!online) {
    return obtenerCuentasLocales()
  }
  try {
    const { data } = await api.get<Cuenta[]>('/cuentas')
    await reemplazarCuentasLocales(
      data.map((c) => ({ id: c.id, nombre: c.nombre, tipo: c.tipo, saldo_actual: c.saldo_actual })),
    )
    return data
  } catch {
    return obtenerCuentasLocales()
  }
}

export async function listarMetodosPago(): Promise<{ id: string; nombre: string }[]> {
  if (!online) {
    return obtenerMetodosLocales()
  }
  try {
    const { data } = await api.get<{ id: string; nombre: string }[]>('/metodos-pago')
    await reemplazarMetodosLocales(data.map((m) => ({ id: m.id, nombre: m.nombre })))
    return data
  } catch {
    return obtenerMetodosLocales()
  }
}

/** ---------- Perfiles ---------- */

export async function listarPerfiles(): Promise<Perfil[]> {
  if (!online) {
    return obtenerPerfilesLocales()
  }
  try {
    // El backend responde {items}. Leerlo como array tiraba el try al catch y
    // dejaba la app sin perfil activo, que es lo que decide que movimientos se
    // ven. Se aceptan las dos formas para no romper con datos viejos.
    const { data } = await api.get<Perfil[] | { items: Perfil[] }>('/perfiles')
    const lista = Array.isArray(data) ? data : data.items ?? []
    for (const p of lista) {
      await guardarPerfilLocal(p)
    }
    return lista
  } catch {
    return obtenerPerfilesLocales()
  }
}

/** ---------- Sincronizacion de cola ---------- */

export async function procesarColaSincronizacion(): Promise<{ ok: number; fail: number }> {
  const cola = await obtenerColaSincronizacion()
  let ok = 0
  let fail = 0

  for (const item of cola) {
    if (!online) break
    try {
      if (item.method === 'POST') {
        // La clave de idempotencia evita duplicar si el envio se corta y se
        // reintenta: el servidor devuelve el movimiento que ya tenia.
        const clave = item.payload?.idempotency_key
        await api.post(
          item.endpoint,
          item.payload,
          clave ? { headers: { 'Idempotency-Key': String(clave) } } : undefined,
        )
      } else if (item.method === 'PATCH') {
        await api.patch(item.endpoint, item.payload)
      } else if (item.method === 'DELETE') {
        await api.delete(item.endpoint)
      }
      await removerDeCola(item.id!)
      ok++
    } catch {
      fail++
      await actualizarReintentos(item.id!, (item.retries ?? 0) + 1)
      // Si ya reintento muchas veces, remover para no bloquear la cola
      if ((item.retries ?? 0) >= 5) {
        await removerDeCola(item.id!)
      }
    }
  }
  return { ok, fail }
}

export async function obtenerEstadoCola(): Promise<number> {
  const cola = await obtenerColaSincronizacion()
  return cola.length
}
