<template>
  <main class="page">
    <h2>AJUSTES</h2>

    <div class="eyebrow">MI CUENTA</div>
    <button class="item" @click="toggle('perfil')">
      <span style="display: flex; gap: 10px; align-items: center">
        <img v-if="me.foto_url" :src="me.foto_url" alt="Tu foto" class="avatar" />
        <i v-else class="bi bi-person-circle" style="font-size: 34px"></i>
        <span>{{ me.nombre }}<br /><small>{{ correoMask }}</small></span>
      </span><span>›</span>
    </button>
    <div v-if="open === 'perfil'" class="panel">
      <div style="text-align: center">
        <img v-if="me.foto_url" :src="me.foto_url" alt="Tu foto" class="avatar-lg" />
        <div>
          <button class="link" @click="fotoInput?.click()">Cambiar foto</button>
          <span v-if="me.foto_url"> · </span>
          <button v-if="me.foto_url" class="link" @click="quitarFoto">Quitar</button>
        </div>
        <input ref="fotoInput" type="file" accept="image/*" hidden @change="elegirFoto" />
        <p v-if="err.foto" class="alert">{{ err.foto }}</p>
      </div>
      <input v-model="nombreEdit" placeholder="Nombre" class="input" />
      <button class="btn-mint" :disabled="busy.perfil" @click="guardarPerfil">
        <span v-if="busy.perfil" class="spinner"></span>Guardar nombre
      </button>
      <p v-if="msg.perfil" class="ok">{{ msg.perfil }}</p>
      <hr class="divider" />
      <div class="eyebrow">CAMBIAR CORREO</div>
      <input v-model="correoNuevo" type="email" placeholder="Nuevo correo" class="input" />
      <input v-model="correoPass" type="password" placeholder="Confirma tu contraseña" class="input" />
      <button class="btn-mint" :disabled="busy.correo" @click="cambiarCorreo">
        <span v-if="busy.correo" class="spinner"></span>Cambiar correo
      </button>
      <p v-if="msg.correo" class="ok">{{ msg.correo }}</p>
      <p v-if="err.correo" class="alert">{{ err.correo }}</p>
      <hr class="divider" />
      <div class="eyebrow">CAMBIAR CONTRASEÑA</div>
      <p class="sub">Te enviamos un código de 10 dígitos a {{ me.correo }}.</p>
      <button class="btn-ghost" :disabled="busy.pw" @click="enviarCodigoPw">
        <span v-if="busy.pw" class="spinner"></span>Enviar código
      </button>
      <input v-model="pw.code" inputmode="numeric" autocomplete="one-time-code" maxlength="10"
        placeholder="Código de 10 dígitos" class="input" style="letter-spacing: 0.25em; text-align: center" />
      <input v-model="pw.nueva" type="password" minlength="8" placeholder="Nueva contraseña (8+)" class="input" />
      <input v-model="pw.conf" type="password" placeholder="Repite la nueva contraseña" class="input" />
      <button class="btn-mint" :disabled="busy.pw" @click="confirmarPassword">
        <span v-if="busy.pw" class="spinner"></span>Guardar contraseña
      </button>
      <p v-if="msg.pw" class="ok">{{ msg.pw }}</p>
      <p v-if="err.pw" class="alert">{{ err.pw }}</p>
    </div>

    <div class="eyebrow">PREFERENCIAS</div>
    <button class="item" @click="toggle('apariencia')"><span>Apariencia</span><span>{{ tema === 'dark' ? 'Oscuro' : 'Claro' }} ›</span></button>
    <div v-if="open === 'apariencia'" class="panel row2">
      <button :class="['chip', tema === 'light' ? 'on' : '']" @click="setTema('light')">Claro</button>
      <button :class="['chip', tema === 'dark' ? 'on' : '']" @click="setTema('dark')">Oscuro</button>
    </div>
    <button class="item" @click="toggle('moneda')"><span>Moneda</span><span>{{ me.moneda }} ›</span></button>
    <div v-if="open === 'moneda'" class="panel row2">
      <button v-for="m in ['COP', 'USD', 'MXN', 'EUR']" :key="m" :class="['chip', monedaEdit === m ? 'on' : '']" @click="monedaEdit = m">{{ m }}</button>
      <button class="btn-mint" :disabled="busy.moneda" @click="guardarMoneda">
        <span v-if="busy.moneda" class="spinner"></span>Guardar
      </button>
    </div>
    <button class="item" @click="toggle('semana')"><span>Inicio de semana</span><span>{{ semana }} ›</span></button>
    <div v-if="open === 'semana'" class="panel row2">
      <button :class="['chip', semana === 'Lunes' ? 'on' : '']" @click="setSemana('Lunes')">Lunes</button>
      <button :class="['chip', semana === 'Domingo' ? 'on' : '']" @click="setSemana('Domingo')">Domingo</button>
    </div>

    <div class="eyebrow">FINANZAS</div>
    <button class="item" @click="toggle('cuentas')"><span>Cuentas ({{ cuentas.length }})</span><span>›</span></button>
    <div v-if="open === 'cuentas'" class="panel">
      <div v-for="c in cuentas" :key="c.id" class="line">
        <span>{{ c.nombre }} <small>· {{ c.tipo }} · ${{ fmt(c.saldo_actual) }}</small></span>
        <button class="btn-ghost" :disabled="busy.cuentas" @click="borrarCuenta(c.id)">Borrar</button>
      </div>
      <input v-model="nc.nombre" placeholder="Nueva cuenta (Ej. Banco)" class="input" />
      <div class="row2">
        <select v-model="nc.tipo" class="input">
          <option value="efectivo">Efectivo</option><option value="banco">Banco</option>
          <option value="bolsa">Bolsa</option><option value="otro">Otro</option>
        </select>
        <NumeroInput v-model="nc.saldo" placeholder="$ inicial" />
      </div>
      <button class="btn-mint" :disabled="busy.cuentas" @click="crearCuenta">
        <span v-if="busy.cuentas" class="spinner"></span>Crear cuenta
      </button>
      <p class="sub">¿Viene del “todo junto” y quieres separar? Crea la cuenta aquí restando del origen, sin hacer cuentas:</p>
      <div class="row2">
        <select v-model="div.origen" class="input">
          <option value="" disabled>Restar de…</option>
          <option v-for="c in cuentas" :key="c.id" :value="c.id">{{ c.nombre }} (${{ fmt(c.saldo_actual) }})</option>
        </select>
        <NumeroInput v-model="div.monto" placeholder="$ a mover" />
      </div>
      <input v-model="div.nombre" placeholder="Nombre nueva cuenta" class="input" />
      <button class="btn-ghost" :disabled="busy.cuentas" @click="dividirCuenta">
        <span v-if="busy.cuentas" class="spinner"></span>Crear restando del origen
      </button>
      <p v-if="msg.cuentas" class="ok">{{ msg.cuentas }}</p>
      <p v-if="err.cuentas" class="alert">{{ err.cuentas }}</p>
    </div>

    <button class="item" @click="toggle('cats')"><span>Categorías ({{ cats.length }})</span><span>›</span></button>
    <div v-if="open === 'cats'" class="panel">
      <div v-for="c in cats" :key="c.id" class="line">
        <span>{{ c.nombre }} <small>· {{ c.tipo }}{{ c.activa ? '' : ' · inactiva' }}</small></span>
        <span>
          <button class="btn-ghost" @click="toggleCat(c)">{{ c.activa ? 'Desactivar' : 'Activar' }}</button>
        </span>
      </div>
      <div class="row2">
        <input v-model="ncat.nombre" placeholder="Nueva categoría" class="input" />
        <select v-model="ncat.tipo" class="input"><option value="gasto">Gasto</option><option value="ingreso">Ingreso</option><option value="ambos">Ambos</option></select>
      </div>
      <button class="btn-mint" :disabled="busy.cats" @click="crearCat">
        <span v-if="busy.cats" class="spinner"></span>Crear categoría
      </button>
      <p v-if="err.cats" class="alert">{{ err.cats }}</p>
    </div>

    <button class="item" @click="toggle('metodos')"><span>Métodos de pago ({{ metodos.length }})</span><span>›</span></button>
    <div v-if="open === 'metodos'" class="panel">
      <div v-for="m in metodos" :key="m.id" class="line">
        <span>{{ m.nombre }}</span>
        <button class="btn-ghost" @click="borrarMetodo(m.id)">Borrar</button>
      </div>
      <div class="row2">
        <input v-model="nmet" placeholder="Nuevo método" class="input" />
        <button class="btn-mint" :disabled="busy.metodos" @click="crearMetodo">
          <span v-if="busy.metodos" class="spinner"></span>Crear
        </button>
      </div>
      <p v-if="err.metodos" class="alert">{{ err.metodos }}</p>
    </div>

    <div class="eyebrow">DATOS Y SEGURIDAD</div>
    <button class="item" @click="toggle('respaldo')"><span>Respaldo y exportación</span><span>›</span></button>    <div v-if="open === 'respaldo'" class="panel">
      <p class="sub" style="margin-bottom: 10px">
        Tus datos son tuyos: el Excel y el JSON salen sin plan. El informe en PDF es
        el único de PRO, porque viene armado para enseñárselo a alguien.
      </p>
      <div class="row2">
        <button class="btn-mint" :disabled="busy.excel" @click="descargarExcel">
          <span v-if="busy.excel" class="spinner"></span>Exportar Excel
        </button>
        <button class="btn-ghost" :disabled="busy.pdf || !esPro" @click="descargarPdf">
          <span v-if="busy.pdf" class="spinner"></span>Informe del mes (PDF)
        </button>
      </div>
      <p v-if="!esPro" class="sub candado">
        <i class="bi bi-lock-fill"></i> El informe en PDF es de PRO. Para respaldar o
        revisar tus datos, el Excel de arriba y el JSON de abajo salen gratis.
      </p>

      <hr class="divider" />
      <div class="row2">
        <button class="btn-mint" :disabled="busy.respaldo" @click="exportar">
          <span v-if="busy.respaldo" class="spinner"></span>Exportar JSON
        </button>
        <select v-model="impModo" class="input"><option value="agregar">Agregar</option><option value="reemplazar">Reemplazar</option></select>
      </div>
      <input type="file" accept=".json" @change="importar" :disabled="busy.respaldo" />
      <input type="file" accept=".xlsx" @change="importarExcel" :disabled="busy.respaldo" />
      <p v-if="msg.respaldo" class="ok">{{ msg.respaldo }}</p>
      <p v-if="err.respaldo" class="alert">{{ err.respaldo }}</p>
      <p v-if="msg.excel" class="ok">{{ msg.excel }}</p>
      <p v-if="err.excel" class="alert">{{ err.excel }}</p>
    </div>

    <div class="item" style="cursor: default">
      <span>2FA por correo<br /><small>{{ twofa ? 'Activado' : 'Protege tu cuenta con un código' }}</small></span>
      <button v-if="!twofa" class="btn-mint" :disabled="busy.twofa" @click="activar2fa">
        <span v-if="busy.twofa" class="spinner"></span>Activar
      </button>
      <button v-else class="btn-ghost" :disabled="busy.twofa" @click="desactivar2fa">
        <span v-if="busy.twofa" class="spinner"></span>Desactivar
      </button>
    </div>
    <p v-if="err.twofa" class="alert">{{ err.twofa }}</p>

    <div class="eyebrow">ZONA DE PELIGRO</div>
    <div class="item" style="cursor: default">
      <span>Empezar desde cero<br /><small>Borra movimientos, presupuestos, metas y cuentas. Tu sesión se conserva.</small></span>
      <button v-if="!armado" class="btn-logout" style="width: auto; margin: 0" @click="armado = true">Reiniciar</button>
      <span v-else style="display: flex; gap: 8px">
        <button class="btn-logout" style="width: auto; margin: 0" :disabled="busy.reset" @click="reiniciar">
          <span v-if="busy.reset" class="spinner"></span>¿Seguro? Toca de nuevo
        </button>
        <button class="btn-ghost" @click="armado = false">No</button>
      </span>
    </div>
    <p v-if="err.reset" class="alert">{{ err.reset }}</p>

    <div class="eyebrow">APP</div>
    <div class="item" style="cursor: default">
      <span>Versión {{ version }}<br /><small>{{ msgUpdate }}</small></span>
      <button class="btn-ghost" :disabled="busy.update" @click="buscarUpdate">
        <span v-if="busy.update" class="spinner"></span>Buscar actualizaciones
      </button>
    </div>
    <div class="item" style="cursor: default; align-items: flex-start">
      <span>Instalar en el teléfono<br /><small>{{ instalarHint }}</small></span>
      <button v-if="!appInstalada" class="btn-mint" @click="instalarAhora">Instalar</button>
      <span v-else class="done-flag">INSTALADA ✓</span>
    </div>
    <p v-if="instalarMsg" class="sub">{{ instalarMsg }}</p>
    <button class="item" @click="toggle('pwa')"><span>Estado de instalación</span><span>›</span></button>
    <div v-if="open === 'pwa'" class="panel">
      <div v-for="c in diag" :key="c.label" class="line">
        <span>{{ c.ok === null ? '○' : c.ok ? '✓' : '✗' }} {{ c.label }}<br /><small>{{ c.detalle }}</small></span>
      </div>
      <button class="btn-ghost" :disabled="busy.pwa" @click="revisarPwa">
        <span v-if="busy.pwa" class="spinner"></span>Revisar ahora
      </button>
    </div>

    <div class="eyebrow">LEGAL</div>
    <button class="item" @click="$router.push('/terminos')"><span>Términos y Condiciones</span><span>›</span></button>
    <button class="item" @click="$router.push('/datos')"><span>Política de Datos</span><span>›</span></button>
    <button class="item" @click="$router.push('/cookies')"><span>Política de Cookies</span><span>›</span></button>

    <button class="btn-logout" :disabled="busy.logout" @click="logout">
      <span v-if="busy.logout" class="spinner"></span>Cerrar sesión
    </button>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import NumeroInput from '../components/NumeroInput.vue'
import api from '../services/api'
import { numero } from '../utils/formato'
import { useAuth } from '../stores/auth'
import { useTema } from '../composables/useTema'
import { usePwaInstall } from '../composables/usePwaInstall'
import { usePwaUpdate } from '../composables/usePwaUpdate'
import { archivoADataURL } from '../composables/useFoto'
const router = useRouter()
const auth = useAuth()
const me = ref({ nombre: '', correo: '', moneda: 'COP', foto_url: null as string | null })
const fotoInput = ref<HTMLInputElement | null>(null)
const cuentas = ref<{ id: string; nombre: string; tipo: string; saldo_actual: number }[]>([])
const cats = ref<{ id: string; nombre: string; tipo: string; activa: boolean }[]>([])
const metodos = ref<{ id: string; nombre: string }[]>([])
const twofa = ref(false)
const armado = ref(false)
const open = ref('')
const version = __APP_VERSION__
const msgUpdate = ref('Al día')
const { hayUpdate, buscando, buscar } = usePwaUpdate()
const { disponible: puedeInstalar, yaInstalada: appInstalada, esIOS, instalar: instalarApp, rescatar: rescatarInstall, diagnosticar } = usePwaInstall()
const diag = ref<{ ok: boolean | null; label: string; detalle: string }[]>([])
const instalarMsg = ref('')
const instalarHint = computed(() =>
  appInstalada.value ? 'Ya la tienes instalada.'
  : puedeInstalar.value ? 'Un toque y queda en tu pantalla principal.'
  : esIOS ? 'En Safari: Compartir → Añadir a pantalla de inicio.'
  : 'Si no sale el aviso, abre el menú ⋮ del navegador → Instalar app.'
)
async function instalarAhora() {
  instalarMsg.value = ''
  const ok = await instalarApp()
  if (!ok && !esIOS) instalarMsg.value = 'El navegador aún no lo ofrece: abre su menú ⋮ → “Instalar app” o “Añadir a pantalla principal”.'
}
async function revisarPwa() {
  busy.pwa = true
  try { diag.value = await diagnosticar() }
  finally { busy.pwa = false }
}
const { tema, aplicar: setTema } = useTema()
const semana = ref(localStorage.getItem('ctd-semana') || 'Lunes')
const nombreEdit = ref('')
const monedaEdit = ref('COP')
const correoNuevo = ref('')
const correoPass = ref('')
const pw = reactive({ code: '', nueva: '', conf: '' })
const nc = reactive({ nombre: '', tipo: 'banco', saldo: null as number | null })
const div = reactive({ origen: '', nombre: '', monto: null as number | null })
const ncat = reactive({ nombre: '', tipo: 'gasto' })
const nmet = ref('')
const impModo = ref('agregar')
const busy = reactive({ perfil: false, moneda: false, correo: false, pw: false, cuentas: false, cats: false, metodos: false, respaldo: false, excel: false, pdf: false, twofa: false, logout: false, update: false, reset: false, pwa: false })
const msg = reactive({ perfil: '', correo: '', pw: '', cuentas: '', respaldo: '', excel: '' })
const err = reactive({ foto: '', correo: '', pw: '', cuentas: '', cats: '', metodos: '', respaldo: '', excel: '', twofa: '', reset: '' })
// El boton se deshabilita si no eres PRO, pero el usuario tiene que poder LEER
// por que esta bloqueado: un boton muerto sin explicacion parece un error.
const esPro = ref(false)
const fmt = (n: number) => numero(n)
const correoMask = computed(() => {
  const [u = '', d = ''] = me.value.correo.split('@')
  if (!d) return me.value.correo
  return `${u.slice(0, 3)}********@${d}`
})

function toggle(k: string) { open.value = open.value === k ? '' : k }
function setSemana(s: string) { semana.value = s; localStorage.setItem('ctd-semana', s) }

async function recargar() {
  const [m, c, ca, me2, e] = await Promise.all([
    api.get('/auth/me'), api.get('/cuentas'),
    api.get('/categorias', { params: { solo_activas: false } }),
    api.get('/metodos-pago'), api.get('/auth/2fa/estado').catch(() => ({ data: { is_2fa_enabled: false } }))
  ])
  me.value = m.data; cuentas.value = c.data; cats.value = ca.data; metodos.value = me2.data
  twofa.value = e.data.is_2fa_enabled
  // Se lee capacidades y no solo plan: el backend es quien decide, no el boton.
  esPro.value = m.data.plan === 'pro' || !!m.data.capacidades?.export_excel
  nombreEdit.value = me.value.nombre; monedaEdit.value = me.value.moneda
}

async function guardarPerfil() {
  busy.perfil = true; msg.perfil = ''
  try { await api.patch('/auth/me', { nombre: nombreEdit.value }); me.value.nombre = nombreEdit.value; msg.perfil = 'Nombre actualizado.' }
  finally { busy.perfil = false }
}
async function elegirFoto(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0]
  if (!file) return
  busy.perfil = true; err.foto = ''
  try {
    const url = await archivoADataURL(file)
    if (url.length > 300_000) { err.foto = 'Foto muy pesada.'; return }
    await api.patch('/auth/me', { foto_url: url })
    me.value.foto_url = url
    msg.perfil = 'Foto actualizada.'
  } catch { err.foto = 'No se pudo subir la foto.'; }
  finally { busy.perfil = false; if (fotoInput.value) fotoInput.value.value = '' }
}
async function quitarFoto() {
  busy.perfil = true
  try { await api.patch('/auth/me', { foto_url: null }); me.value.foto_url = null }
  finally { busy.perfil = false }
}
async function guardarMoneda() {
  busy.moneda = true
  try { await api.patch('/auth/me', { moneda: monedaEdit.value }); me.value.moneda = monedaEdit.value }
  finally { busy.moneda = false }
}
async function cambiarCorreo() {
  busy.correo = true; err.correo = ''; msg.correo = ''
  try {
    const { data } = await api.post('/auth/correo/cambiar', { nuevo_correo: correoNuevo.value.trim().toLowerCase(), password: correoPass.value })
    me.value.correo = data.correo; correoNuevo.value = ''; correoPass.value = ''
    msg.correo = 'Correo actualizado.'
  } catch (e: unknown) {
    const r = (e as { response?: { status?: number; data?: { detail?: string } } }).response
    err.correo = r?.status === 401 ? 'Contraseña incorrecta.' : (r?.data?.detail ?? 'No se pudo cambiar.')
  } finally { busy.correo = false }
}
async function enviarCodigoPw() {
  busy.pw = true; err.pw = ''; msg.pw = ''
  try { await api.post('/auth/password/solicitar', { correo: me.value.correo }); msg.pw = 'Código de 10 dígitos enviado. Revisa tu correo.' }
  catch (e: unknown) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
    err.pw = d ?? 'No se pudo enviar.'
  } finally { busy.pw = false }
}
async function confirmarPassword() {
  err.pw = ''; msg.pw = ''
  if (pw.nueva !== pw.conf) { err.pw = 'Las contraseñas no coinciden.'; return }
  busy.pw = true
  try {
    await api.post('/auth/password/confirmar', { correo: me.value.correo, code: pw.code, nueva_password: pw.nueva })
    pw.code = ''; pw.nueva = ''; pw.conf = ''
    msg.pw = 'Contraseña actualizada.'
  } catch { err.pw = 'Código inválido o vencido (10 min, 5 intentos).' }
  finally { busy.pw = false }
}
async function crearCuenta() {
  busy.cuentas = true; err.cuentas = ''; msg.cuentas = ''
  try { await api.post('/cuentas', { nombre: nc.nombre, tipo: nc.tipo, saldo_inicial: nc.saldo || 0 }); nc.nombre = ''; nc.saldo = 0; msg.cuentas = 'Cuenta creada.'; await recargar() }
  catch { err.cuentas = 'No se pudo crear.'; }
  finally { busy.cuentas = false }
}
async function dividirCuenta() {
  busy.cuentas = true; err.cuentas = ''; msg.cuentas = ''
  try {
    await api.post('/cuentas/dividir', { origen_id: div.origen, nombre: div.nombre, monto: div.monto })
    div.origen = ''; div.nombre = ''; div.monto = null; msg.cuentas = 'Cuenta creada restando del origen.'
    await recargar()
  } catch (e: unknown) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
    err.cuentas = typeof d === 'string' ? d : 'No se pudo dividir (¿origen con movimientos o monto mayor?).'
  } finally { busy.cuentas = false }
}
async function borrarCuenta(id: string) {
  if (!confirm('¿Borrar cuenta? Solo vacías y sin movimientos.')) return
  busy.cuentas = true; err.cuentas = ''
  try { await api.delete(`/cuentas/${id}`); await recargar() }
  catch { err.cuentas = 'No se puede borrar: transfiere o elimina movimientos primero.' }
  finally { busy.cuentas = false }
}
async function crearCat() {
  busy.cats = true; err.cats = ''
  try { await api.post('/categorias', { nombre: ncat.nombre, tipo: ncat.tipo, icono: 'tag' }); ncat.nombre = ''; await recargar() }
  catch { err.cats = 'Ya existe o datos inválidos.' }
  finally { busy.cats = false }
}
async function toggleCat(c: { id: string; activa: boolean }) {
  await api.patch(`/categorias/${c.id}`, { activa: !c.activa }); await recargar()
}
async function crearMetodo() {
  busy.metodos = true; err.metodos = ''
  try { await api.post('/metodos-pago', { nombre: nmet.value }); nmet.value = ''; await recargar() }
  catch { err.metodos = 'Ya existe o es inválido.' }
  finally { busy.metodos = false }
}
async function borrarMetodo(id: string) {
  try { await api.delete(`/metodos-pago/${id}`); await recargar() }
  catch { err.metodos = 'Tiene movimientos: no se puede borrar.' }
}
async function exportar() {
  busy.respaldo = true; err.respaldo = ''; msg.respaldo = ''
  try {
    const { data } = await api.get('/respaldo/export')
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob); a.download = 'ctd-respaldo.json'; a.click()
    msg.respaldo = 'Respaldo descargado.'
  } catch { err.respaldo = 'No se pudo exportar.' }
  finally { busy.respaldo = false }
}

// Descargar un blob del backend. Se usa la misma ruta para el Excel y el PDF:
// lo unico que cambia es el nombre del archivo, y el nombre debe venir del
// Content-Disposition del servidor para que el usuario reconozca su propio perfil.
function _bajar(blob: Blob, nombre: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = nombre; a.click()
  // Sin revocar, cada descarga deja el blob colgado en memoria del navegador.
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
function _nombreDe(respuesta: { headers: Record<string, unknown> }, porDefecto: string) {
  const cd = String(respuesta.headers?.['content-disposition'] ?? '')
  const m = /filename\*=UTF-8''([^;]+)/i.exec(cd)
  return m ? decodeURIComponent(m[1]) : porDefecto
}
async function descargarExcel() {
  busy.excel = true; err.excel = ''; msg.excel = ''
  try {
    const r = await api.get('/documentos/excel', { responseType: 'blob' })
    _bajar(r.data, _nombreDe(r, 'ctd.xlsx'))
    msg.excel = 'Excel descargado.'
  } catch (e: any) {
    err.excel = e?.response?.status === 402
      ? 'El Excel es de PRO. Para respaldar gratis, usa el JSON de abajo.'
      : 'No se pudo generar el Excel.'
  } finally { busy.excel = false }
}
async function descargarPdf() {
  busy.pdf = true; err.excel = ''; msg.excel = ''
  try {
    const r = await api.get('/documentos/reporte.pdf', { responseType: 'blob' })
    _bajar(r.data, _nombreDe(r, 'informe.pdf'))
    msg.excel = 'Informe descargado.'
  } catch (e: any) {
    err.excel = e?.response?.status === 402
      ? 'El informe en PDF es de PRO. Activa tu plan para descargarlo.'
      : 'No se pudo generar el informe.'
  } finally { busy.pdf = false }
}
async function importarExcel(ev: Event) {
  const f = (ev.target as HTMLInputElement).files?.[0]
  if (!f) return
  busy.respaldo = true; err.excel = ''; msg.excel = ''
  try {
    const fd = new FormData()
    fd.append('archivo', f)
    const { data } = await api.post('/documentos/importar-excel', fd)
    const detalle = data.errores?.length ? ` Con ${data.errores.length} avisos.` : ''
    msg.excel = `Entraron ${data.creados}, se omitieron ${data.omitidos_duplicados} repetidos.${detalle}`
    await recargar()
  } catch (e: any) {
    // El backend responde el motivo exacto ("la fecha 'el jueves' no se
    // entiende"), que es justo lo que el usuario necesita para arreglar el archivo.
    err.excel = e?.response?.data?.detail ?? 'No se pudo leer el archivo.'
  } finally {
    busy.respaldo = false
    ;(ev.target as HTMLInputElement).value = ''
  }
}
async function importar(ev: Event) {
  const f = (ev.target as HTMLInputElement).files?.[0]
  if (!f) return
  busy.respaldo = true; err.respaldo = ''; msg.respaldo = ''
  try {
    const payload = JSON.parse(await f.text())
    const { data } = await api.post('/respaldo/import', payload, { params: { modo: impModo.value } })
    msg.respaldo = `Importados ${data.creados}, omitidos ${data.omitidos_duplicados}.`
    await recargar()
  } catch { err.respaldo = 'Archivo inválido.' }
  finally { busy.respaldo = false }
}
async function activar2fa() {
  busy.twofa = true; err.twofa = ''
  try {
    await api.post('/auth/2fa/solicitar', { correo: me.value.correo })
    router.push({ path: '/2fa', query: { modo: 'activar' } })
  } catch (e: unknown) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
    err.twofa = d ?? 'No se pudo enviar el código.'
  } finally { busy.twofa = false }
}
async function desactivar2fa() {
  busy.twofa = true
  try { await api.post('/auth/2fa/desactivar'); twofa.value = false }
  finally { busy.twofa = false }
}
async function logout() { busy.logout = true; await auth.logout(); router.push('/') }
async function reiniciar() {
  busy.reset = true; err.reset = ''
  try {
    await api.post('/auth/cuenta/reiniciar', null, { params: { confirm: true } })
    auth.setOnboarding(false)
    router.push('/onboarding')
  } catch { err.reset = 'No se pudo reiniciar.'; armado.value = false }
  finally { busy.reset = false }
}
async function buscarUpdate() {
  busy.update = true
  msgUpdate.value = 'Buscando…'
  await buscar()
  setTimeout(() => {
    busy.update = false
    msgUpdate.value = hayUpdate.value ? 'Hay una versión nueva: usa el banner.' : 'Estás al día.'
  }, 4500)
}

onMounted(async () => { rescatarInstall(); await recargar() })
</script>

<style>
.eyebrow{margin:18px 0 6px}
.item{display:flex;justify-content:space-between;align-items:center;gap:8px;width:100%;padding:12px 2px;border:0;border-bottom:1px solid var(--line);background:none;font:inherit;color:inherit;text-align:left;cursor:pointer}
.item small{opacity:.65}
.panel{display:grid;gap:10px;padding:12px 2px 16px;border-bottom:1px solid var(--line)}
.row2{display:flex;gap:8px;flex-wrap:wrap}
.row2 .input,.row2 .chip{flex:1;min-width:120px}
.line{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:8px 0;border-bottom:1px dashed var(--line)}
.line small{opacity:.65}
.chip{border:1px solid var(--navy);background:var(--surface);color:var(--navy);border-radius:99px;padding:8px 14px;font-weight:700}
.chip.on{background:var(--navy);color:#fff}
.ok{color:#00B37A;font-size:13px}
.sub{font-size:13px;opacity:.65}
.btn-logout{margin-top:16px;width:100%;padding:14px;border-radius:14px;background:var(--surface);color:var(--danger);border:1px solid var(--danger);font-weight:800;cursor:pointer}
.btn-logout:disabled{opacity:.6;cursor:wait}
.candado{display:flex;gap:6px;align-items:flex-start;margin:0;color:var(--warning);opacity:1;font-size:12.5px;line-height:1.45}
.candado i{margin-top:2px;flex:none}
</style>
