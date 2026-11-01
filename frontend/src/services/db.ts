import { openDB, type DBSchema, type IDBPDatabase } from 'idb'

type MovimientoLocal = {
  id: string
  perfil_id?: string
  tipo: 'ingreso' | 'gasto'
  monto: number
  descripcion: string
  categoria: string | null
  cuenta: string | null
  fecha: string
  cuenta_id: string | null
  categoria_id: string | null
  metodo_id: string | null
  recurrente_id: string | null
  idempotency_key: string | null
  created_at: string
}

type RecurrenteLocal = {
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
  created_at: string
}

type PerfilLocal = {
  id: string
  user_id: string
  nombre: string
  tipo: string
  principal: boolean
  notificar_mezcla: boolean
  created_at: string
}

/** Cuenta cacheada: sin esto el formulario de movimiento no tiene como elegir
 *  cuenta cuando no hay red, y la cuenta es obligatoria al guardar. */
type CuentaLocal = {
  id: string
  nombre: string
  tipo?: string
  saldo_actual?: number
}

type MetodoLocal = {
  id: string
  nombre: string
}

type SyncItem = {
  id?: number
  type: 'movimiento' | 'recurrente' | 'eliminar_movimiento' | 'eliminar_recurrente'
  payload: any
  method: 'POST' | 'PATCH' | 'DELETE'
  endpoint: string
  created_at: string
  retries: number
}

export type { MovimientoLocal, RecurrenteLocal, CuentaLocal, MetodoLocal }

interface CTDDB extends DBSchema {
  movimientos: {
    key: string
    value: MovimientoLocal
    indexes: { 'by-fecha': string; 'by-perfil': string }
  }
  categorias: {
    key: string
    value: { id: string; nombre: string; tipo: string }
    indexes: { 'by-tipo': string }
  }
  cuentas: {
    key: string
    value: CuentaLocal
  }
  metodos: {
    key: string
    value: MetodoLocal
  }
  recurrentes: {
    key: string
    value: RecurrenteLocal
    indexes: { 'by-perfil': string }
  }
  perfiles: {
    key: string
    value: PerfilLocal
  }
  sync_queue: {
    key: number
    value: SyncItem
    indexes: { 'by-created': string }
  }
}

const DB_NAME = 'ctd-db'
// Version 2 agrega cuentas y metodos de pago. Al subir la version hay que crear
// tambien los almacenes que falten en bases ya existentes: si solo se crearan
// con oldVersion === 0, un usuario que ya abrio la app antes se quedaria con
// "objectStore not found" al volver y nada se guardaria.
const DB_VERSION = 2

let dbPromise: Promise<IDBPDatabase<CTDDB>> | null = null

export function getDB(): Promise<IDBPDatabase<CTDDB>> {
  if (!dbPromise) {
    dbPromise = openDB<CTDDB>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains('movimientos')) {
          const mov = db.createObjectStore('movimientos', { keyPath: 'id' })
          mov.createIndex('by-fecha', 'fecha')
          mov.createIndex('by-perfil', 'perfil_id')
        }
        if (!db.objectStoreNames.contains('categorias')) {
          const cat = db.createObjectStore('categorias', { keyPath: 'id' })
          cat.createIndex('by-tipo', 'tipo')
        }
        if (!db.objectStoreNames.contains('cuentas')) {
          db.createObjectStore('cuentas', { keyPath: 'id' })
        }
        if (!db.objectStoreNames.contains('metodos')) {
          db.createObjectStore('metodos', { keyPath: 'id' })
        }
        if (!db.objectStoreNames.contains('recurrentes')) {
          const rec = db.createObjectStore('recurrentes', { keyPath: 'id' })
          rec.createIndex('by-perfil', 'perfil_id')
        }
        if (!db.objectStoreNames.contains('perfiles')) {
          db.createObjectStore('perfiles', { keyPath: 'id' })
        }
        if (!db.objectStoreNames.contains('sync_queue')) {
          const sync = db.createObjectStore('sync_queue', { keyPath: 'id', autoIncrement: true })
          sync.createIndex('by-created', 'created_at')
        }
      },
    })
  }
  return dbPromise
}

/** Movimiento local */
export async function guardarMovimientoLocal(m: MovimientoLocal): Promise<void> {
  const db = await getDB()
  await db.put('movimientos', m)
}

export async function obtenerMovimientosLocales(perfilId?: string): Promise<MovimientoLocal[]> {
  const db = await getDB()
  const tx = db.transaction('movimientos', 'readonly')
  const store = tx.store
  let index: any = store
  if (perfilId) {
    index = store.index('by-perfil')
  }
  const all = await (perfilId ? index.getAll(perfilId) : store.getAll())
  await tx.done
  return all
}

export async function eliminarMovimientoLocal(id: string): Promise<void> {
  const db = await getDB()
  await db.delete('movimientos', id)
}

/** Recurrente local */
export async function guardarRecurrenteLocal(r: RecurrenteLocal): Promise<void> {
  const db = await getDB()
  await db.put('recurrentes', r)
}

export async function obtenerRecurrentesLocales(perfilId?: string): Promise<RecurrenteLocal[]> {
  const db = await getDB()
  const tx = db.transaction('recurrentes', 'readonly')
  const store = tx.store
  let index: any = store
  if (perfilId) {
    index = store.index('by-perfil')
  }
  const all = await (perfilId ? index.getAll(perfilId) : store.getAll())
  await tx.done
  return all
}

export async function eliminarRecurrenteLocal(id: string): Promise<void> {
  const db = await getDB()
  await db.delete('recurrentes', id)
}

/** Perfil local */
export async function guardarPerfilLocal(p: PerfilLocal): Promise<void> {
  const db = await getDB()
  await db.put('perfiles', p)
}

export async function obtenerPerfilesLocales(): Promise<PerfilLocal[]> {
  const db = await getDB()
  const all = await db.getAll('perfiles')
  return all
}

/** Categoría local */

export async function guardarCategoriaLocal(c: { id: string; nombre: string; tipo: string }): Promise<void> {
  const db = await getDB()
  await db.put('categorias', c)
}

export async function obtenerCategoriasLocales(): Promise<{ id: string; nombre: string; tipo: string }[]> {
  const db = await getDB()
  return db.getAll('categorias')
}

export async function eliminarCategoriaLocal(id: string): Promise<void> {
  const db = await getDB()
  await db.delete('categorias', id)
}

/** Cuentas y metodos de pago: catalogos que el formulario necesita sin red. */

export async function reemplazarCuentasLocales(cuentas: CuentaLocal[]): Promise<void> {
  const db = await getDB()
  const tx = db.transaction('cuentas', 'readwrite')
  await tx.store.clear()
  for (const c of cuentas) await tx.store.put(c)
  await tx.done
}

export async function obtenerCuentasLocales(): Promise<CuentaLocal[]> {
  const db = await getDB()
  return db.getAll('cuentas')
}

export async function reemplazarMetodosLocales(metodos: MetodoLocal[]): Promise<void> {
  const db = await getDB()
  const tx = db.transaction('metodos', 'readwrite')
  await tx.store.clear()
  for (const m of metodos) await tx.store.put(m)
  await tx.done
}

export async function obtenerMetodosLocales(): Promise<MetodoLocal[]> {
  const db = await getDB()
  return db.getAll('metodos')
}

/** Cola de sincronizacion */
export async function encolarSincronizacion(item: Omit<SyncItem, 'id' | 'created_at' | 'retries'>): Promise<void> {
  const db = await getDB()
  await db.add('sync_queue', {
    ...item,
    created_at: new Date().toISOString(),
    retries: 0,
  })
}

export async function obtenerColaSincronizacion(): Promise<SyncItem[]> {
  const db = await getDB()
  return db.getAllFromIndex('sync_queue', 'by-created')
}

export async function removerDeCola(id: number): Promise<void> {
  const db = await getDB()
  await db.delete('sync_queue', id)
}

export async function actualizarReintentos(id: number, retries: number): Promise<void> {
  const db = await getDB()
  const item = await db.get('sync_queue', id)
  if (item) {
    item.retries = retries
    await db.put('sync_queue', item)
  }
}

export async function limpiarColaSincronizacion(): Promise<void> {
  const db = await getDB()
  await db.clear('sync_queue')
}

export async function cerrarDB() {
  const db = await getDB()
  db.close()
  dbPromise = null
}
