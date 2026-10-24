// Verificación temporal: un solo acceso primario de registro (se borra al terminar).
import { chromium } from 'playwright'

const BASE = 'https://localhost:4175'
const hoy = new Date().toISOString().slice(0, 10)
const fallos = []
const ok = (cond, msg) => {
  console.log(`${cond ? 'OK  ' : 'FALLA'} ${msg}`)
  if (!cond) fallos.push(msg)
}

const browser = await chromium.launch({ channel: 'chrome' })

async function preparar(viewport) {
  const ctx = await browser.newContext({ viewport, ignoreHTTPSErrors: true, serviceWorkers: 'block' })
  const page = await ctx.newPage()
  const errores = []
  page.on('pageerror', (e) => errores.push(e.message))
  page.on('console', (m) => { if (m.type() === 'error') errores.push(m.text()) })
  await page.addInitScript(() => {
    localStorage.setItem('access_token', 'fake')
    localStorage.setItem('refresh_token', 'fake')
    localStorage.setItem('ctd-onboarding', '1')
    localStorage.setItem('ctd-install-no', '1')
    localStorage.setItem('ctd-tour-v4', JSON.stringify({ visto: true }))
  })
  await page.route('**/api/v1/**', async (route) => {
    const req = route.request()
    const ruta = new URL(req.url()).pathname.replace('/api/v1', '')
    const json = (b) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(b) })
    if (ruta === '/auth/me') return json({ id: 'u1', nombre: 'Ana', correo: 'a@x.co', moneda: 'COP', pais: 'CO', pais_nombre: 'Colombia', usa_quincena: true, onboarding_done: true, acepta_datos: true, foto_url: null })
    if (ruta === '/cuentas') return json([{ id: 'c1', nombre: 'Ahorros', tipo: 'ahorro', saldo_actual: 100000 }])
    if (ruta === '/categorias') return json([{ id: 'k1', nombre: 'Comida', tipo: 'gasto', activa: true }])
    if (ruta === '/metodos-pago') return json([])
    if (ruta === '/captura/uso') return json({ queda: 9, limite: 10 })
    if (ruta === '/movimientos') return json({ items: [{ id: 'm1', tipo: 'gasto', monto: 12000, fecha: hoy, descripcion: 'Almuerzo', categoria_id: 'k1', cuenta_id: 'c1' }] })
    return json({})
  })
  return { ctx, page, errorres: [] }
}