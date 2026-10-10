<template>
  <main class="land">
    <!-- HERO -->
    <section class="land-hero">
      <div class="land-inner">
        <div>
          <p class="eyebrow" style="color: var(--mint)">CTD · CONTROLA TU DINERO</p>
          <h1 class="display">Registra. Entiende.<br />Decide. <span style="color: var(--mint)">Avanza.</span></h1>
          <p class="land-sub">La PWA de finanzas personales que convierte tus movimientos en decisiones claras. Sin tecnicismos, sin vueltas.</p>
          <div class="land-ctas">
            <button class="land-cta" @click="$router.push(authed ? '/inicio' : '/registro')">
              {{ authed ? 'Abrir mi app' : 'Crear cuenta gratis' }}
            </button>
            <button v-if="!authed" class="land-ghost" @click="$router.push('/login')">Entrar</button>
          </div>
          <p class="sub">Instalable · Funciona sin conexión · Tus datos son exportables</p>
        </div>
        <div class="phone" aria-hidden="false" aria-label="Demostración interactiva">
          <div class="phone-screen">
            <div class="eyebrow">DISPONIBLE</div>
            <div class="display" :class="{ tick: pulse.includes('disp') }" :style="{ color: dDisp < 0 ? 'var(--danger)' : undefined }">${{ fmt(dDisp) }}</div>
            <div :class="bal >= 0 ? 't-pos' : 't-neg'" style="font-weight: 800">Balance {{ bal >= 0 ? '+' : '−' }}${{ fmt(Math.abs(bal)) }} · {{ balPct }}% disponible</div>
            <hr class="divider" />
            <div class="grid-2">
              <div><div class="eyebrow">INGRESOS</div><strong :class="{ tick: pulse.includes('ing') }">${{ fmt(dIng) }}</strong></div>
              <div><div class="eyebrow">GASTOS</div><strong :class="{ tick: pulse.includes('gas') }">${{ fmt(dGas) }}</strong></div>
            </div>
            <hr class="divider" />
            <div class="eyebrow">META</div>
            <div><strong>{{ metaNombre }}</strong></div>
            <div class="progress" style="margin: 8px 0" :class="{ tick: pulse.includes('meta') }"><span :style="{ width: metaPct + '%' }"></span></div>
            <p class="sub">{{ metaPct }}%<span v-if="metaFalt > 0"> · Faltan ${{ fmt(metaFalt) }}</span><span v-else> · ¡Meta cumplida!</span></p>
            <p class="sub">Las metas son seguimiento; no apartan dinero real.</p>
            <div v-if="!demoActivo" style="margin-top: 12px">
              <button class="land-cta" style="width: 100%; padding: 12px; font-size: 15px" @click="demoActivo = true">Pruébalo</button>
            </div>
            <div v-else class="demo-btns">
              <button @click="demoIngreso" title="Agregar ingreso demo"><i class="bi bi-plus-lg"></i><span>+ $200 mil</span></button>
              <button @click="demoGasto" title="Agregar gasto demo"><i class="bi bi-dash-lg"></i><span>− $85 mil</span></button>
              <button @click="demoAporte" title="Aportar a la meta"><i class="bi bi-piggy-bank"></i><span>Meta +$100 mil</span></button>
              <button @click="demoReset" title="Reiniciar demo"><i class="bi bi-arrow-counterclockwise"></i><span>Reiniciar</span></button>
            </div>
            <p class="sub demo-hint">Demo: toca los botones y mira cómo reacciona tu dinero.</p>
          </div>
        </div>
      </div>
      <span class="glow-line"></span>
    </section>

    <!-- TICKER (duplicado solo si puede animar; si no, texto único centrado) -->
    <div class="ticker" aria-hidden="true">
      <div v-if="!lite" class="marquee-track">
        <span v-for="i in 2" :key="i">REGISTRA · ENTIENDE · DECIDE · AVANZA ·&nbsp;</span>
      </div>
      <div v-else class="ticker-static">REGISTRA · ENTIENDE · DECIDE · AVANZA</div>
    </div>

    <!-- MÓDULOS: editorial, no tarjetas -->
    <section class="land-section">
      <Reveal><h2 class="display">Todo tu dinero,<br />una sola lectura.</h2></Reveal>
      <div class="ed-list">
        <Reveal v-for="(f, i) in modulos" :key="f.t">
          <div class="ed-row"><span class="ed-n">0{{ i + 1 }}</span>
            <div><strong>{{ f.t }}</strong><p class="sub">{{ f.d }}</p></div>
            <span class="ed-arrow">→</span>
          </div>
        </Reveal>
      </div>
    </section>

    <!-- COLOR CON SIGNIFICADO: bandas grandes -->
    <section class="land-section">
      <Reveal><h2 class="display">El color tiene significado.</h2>
      <p class="sub">En CTD el color no decora: informa.</p></Reveal>
      <Reveal>
        <div class="bands">
          <div class="band navy"><strong>NAVY</strong><span>estructura · confianza</span></div>
          <div class="band-row">
            <div class="band mint"><strong>MINT</strong><span>progreso</span></div>
            <div class="band red"><strong>ROJO</strong><span>alerta</span></div>
          </div>
          <div class="band amber"><strong>ÁMBAR</strong><span>límite cercano</span></div>
        </div>
      </Reveal>
    </section>

    <!-- CADENA DEL DINERO -->
    <section class="land-section">
      <Reveal><h2 class="display">Tu dinero cambia.<br />Tú lo ves.</h2>
      <p class="sub">Cada movimiento recorre tu sistema:</p></Reveal>
      <div class="chain" aria-hidden="true">
        <div v-for="(n, i) in cadena" :key="n" class="chain-node" :style="{ animationDelay: `${i * 0.8}s` }">{{ n }}</div>
      </div>
    </section>

    <!-- CÓMO FUNCIONA -->
    <section class="land-section">
      <Reveal><h2 class="display">Empieza en 1 minuto.</h2></Reveal>
      <ol class="steps">
        <Reveal v-for="(p, i) in pasos" :key="p.t"><li><span class="step-n">{{ i + 1 }}</span><div><strong>{{ p.t }}</strong><p class="sub">{{ p.d }}</p></div></li></Reveal>
      </ol>
      <button class="land-cta" @click="$router.push(authed ? '/inicio' : '/registro')">
        {{ authed ? 'Abrir mi app' : 'Crear cuenta gratis' }}
      </button>
    </section>

    <footer class="land-foot sub">CTD · Controla Tu Dinero — PWA instalable. Tus datos, tus decisiones.<br /><a href="#" @click.prevent="$router.push('/terminos')">Términos</a> · <a href="#" @click.prevent="$router.push('/datos')">Datos</a> · <a href="#" @click.prevent="$router.push('/cookies')">Cookies</a></footer>
  </main>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import type { Ref } from 'vue'
import Reveal from '../components/Reveal.vue'
import { animacionesOff } from '../composables/usePerf'
import { useAuth } from '../stores/auth'
import { numero } from '../utils/formato'
const auth = useAuth()
const authed = computed(() => auth.isAuthed)
const lite = document.documentElement.dataset.perf !== 'full'
// Demo interactiva del hero (datos locales, sin backend)
// DISPONIBLE arranca en el balance del mes: coherente (ing − gas = disp).
const demoActivo = ref(false)
const pulse = ref('')
const demo = reactive({ ing: 2500000, gas: 1740000, disp: 760000, ahorrado: 2880000, objetivo: 4000000 })
const dIng = ref(demo.ing); const dGas = ref(demo.gas); const dDisp = ref(demo.disp); const dAhor = ref(demo.ahorrado)
const metaNombre = 'Computador'
const bal = computed(() => dIng.value - dGas.value)
const balPct = computed(() => (dIng.value > 0 ? Math.round((bal.value / dIng.value) * 100) : 0))
const metaPct = computed(() => Math.min(Math.round((dAhor.value / demo.objetivo) * 100), 100))
const metaFalt = computed(() => Math.max(demo.objetivo - dAhor.value, 0))
const fmt = (n: number) => numero(n)
function tween(target: Ref<number>, to: number) {
  if (animacionesOff()) {
    target.value = to
    return
  }
  const from = target.value
  const t0 = performance.now()
  const dur = 450
  function step(t: number) {
    const p = Math.min((t - t0) / dur, 1)
    const e = 1 - Math.pow(1 - p, 3)
    target.value = Math.round(from + (to - from) * e)
    if (p < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
}
function sync() {
  tween(dIng, demo.ing); tween(dGas, demo.gas); tween(dDisp, demo.disp); tween(dAhor, demo.ahorrado)
}
function marcar(cual: string) {
  if (!pulse.value.includes(cual)) pulse.value = `${pulse.value} ${cual}`.trim()
  clearTimeout((marcar as unknown as { t?: ReturnType<typeof setTimeout> }).t)
  ;(marcar as unknown as { t?: ReturnType<typeof setTimeout> }).t = setTimeout(() => { pulse.value = '' }, 500)
}
function demoIngreso() { demo.ing += 200000; demo.disp += 200000; marcar('ing'); marcar('disp'); sync() }
function demoGasto() { demo.gas += 85000; demo.disp -= 85000; marcar('gas'); marcar('disp'); sync() }
function demoAporte() { demo.ahorrado = Math.min(demo.ahorrado + 100000, demo.objetivo); marcar('meta'); sync() }
function demoReset() {
  demo.ing = 2500000; demo.gas = 1740000; demo.disp = 760000; demo.ahorrado = 2880000
  sync()
}
const modulos = [
  { t: 'MOVIMIENTOS', d: 'Registra lo que entra y sale. Sin formularios interminables.' },
  { t: 'PLAN', d: 'Convierte tus números en objetivos concretos.' },
  { t: 'DATOS', d: 'Entiende qué está pasando, en tu idioma.' },
  { t: 'INICIO', d: '¿Cómo estoy hoy? Una pantalla, cero ruido.' }
]
const cadena = ['+ $500.000', 'Disponible', 'Presupuesto', 'Meta', 'Balance']
const pasos = [
  { t: 'Crea tu cuenta', d: 'Nombre, correo y tu moneda principal. Tus cuentas y saldos se configuran dentro de la app.' },
  { t: 'Registra en segundos', d: 'Un botón + gigante, también en tu teléfono.' },
  { t: 'Decide con claridad', d: 'Balance, presupuestos y metas conectados.' }
]
</script>

<style>
.land { background: var(--bg); }
.land-hero { background: linear-gradient(135deg, #050B3B 0%, #0A1763 100%); color: #fff; position: relative; overflow: hidden; }
.land-inner { max-width: 960px; margin: 0 auto; padding: 56px 20px; display: grid; gap: 32px; }
.land-hero h1 { font-size: clamp(38px, 7vw, 64px); line-height: 1.02; margin: 12px 0; }
.land-sub { opacity: 0.8; font-size: 18px; max-width: 46ch; }
.land-ctas { display: flex; gap: 12px; margin: 20px 0 12px; flex-wrap: wrap; }
.land-cta { background: var(--mint); color: var(--navy); border: 0; border-radius: 16px; padding: 16px 28px; font-weight: 800; font-size: 17px; cursor: pointer; transition: transform 180ms ease; }
.land-cta:hover { transform: translateY(-2px); }
.land-ghost { background: transparent; color: #fff; border: 1px solid rgba(255,255,255,.4); border-radius: 16px; padding: 16px 28px; font-weight: 700; cursor: pointer; }
.land-hero .sub { color: #B9C2E0; }
.land-hero .glow-line { position: absolute; left: 0; right: 0; bottom: 0; height: 3px; background: linear-gradient(90deg, transparent, var(--mint), transparent); transform-origin: left; animation: glowline 2.8s ease-in-out infinite; }
/* Mockup CSS del dashboard */
.phone { width: min(340px, 100%); border-radius: 30px; border: 1px solid rgba(255,255,255,.25); padding: 12px; background: rgba(255,255,255,.06); animation: floaty 5s ease-in-out infinite; }
.phone-screen { background: #fff; color: var(--ink); border-radius: 20px; padding: 18px; }
.phone-screen .eyebrow { color: var(--ink-soft); }
/* Botonera de la demo interactiva */
.demo-btns { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }
.demo-btns button {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  border: 1px solid var(--navy); background: var(--surface);
  color: var(--navy); border-radius: 12px; padding: 10px 6px;
  font-size: 13px; font-weight: 800; cursor: pointer;
}
.demo-btns button:active { transform: scale(0.96); }
.demo-hint { margin-top: 8px; font-size: 12px; }
.phone-screen .land-cta { width: 100%; padding: 12px; font-size: 15px; }
.ticker-static { text-align: center; }
@keyframes floaty { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
/* Tick elegante al tocar la demo */
.tick { display: inline-block; animation: tick 0.45s ease; }
div.tick { display: block; }
@keyframes tick { 0% { transform: scale(1); } 35% { transform: scale(1.06); } 100% { transform: scale(1); } }
/* Ticker discreto */
.ticker { background: var(--mint); color: var(--navy); overflow: hidden; font-weight: 700; letter-spacing: 0.08em; font-size: 12px; padding: 7px 0; }
.marquee-track { display: inline-block; white-space: nowrap; animation: marquee 18s linear infinite; }
@keyframes marquee { to { transform: translateX(-50%); } }
/* Secciones */
.land-section { max-width: 960px; margin: 0 auto; padding: 44px 20px 8px; content-visibility: auto; contain-intrinsic-size: 400px; }
.land-section h2 { font-size: clamp(28px, 5vw, 42px); margin: 0 0 8px; }
/* Módulos editoriales */
.ed-list { display: grid; margin-top: 8px; }
.ed-row { display: flex; align-items: baseline; gap: 14px; padding: 18px 2px; border-bottom: 1px solid var(--line); }
.ed-n { font-weight: 800; color: var(--mint-dark); font-size: 14px; flex: none; }
.ed-row strong { font-size: 19px; letter-spacing: 0.02em; }
.ed-row .sub { margin: 4px 0 0; }
.ed-arrow { margin-left: auto; font-size: 22px; color: var(--mint-dark); flex: none; }
/* Bandas de color */
.bands { display: grid; gap: 10px; margin-top: 16px; }
.band { border-radius: 18px; padding: 26px 20px; display: flex; align-items: baseline; gap: 12px; }
.band strong { font-size: clamp(26px, 5vw, 40px); letter-spacing: 0.02em; }
.band span { font-size: 14px; opacity: 0.85; }
.band.navy { background: var(--navy); color: #fff; }
.band.mint { background: var(--mint); color: var(--navy); }
.band.red { background: var(--danger); color: #fff; }
.band.amber { background: var(--warning); color: var(--navy); }
.band-row { display: grid; gap: 10px; }
@media (min-width: 640px) { .band-row { grid-template-columns: 1fr 1fr; } }
/* Cadena del dinero */
.chain { display: flex; flex-direction: column; align-items: stretch; gap: 2px; margin-top: 16px; }
.chain-node {
  text-align: center; font-weight: 800; font-size: 17px;
  border: 1px solid var(--line); background: var(--surface); color: var(--ink);
  border-radius: 14px; padding: 12px;
  animation: chainpulse 4s ease-in-out infinite;
}
.chain-node:first-child { border-color: var(--mint-dark); color: var(--mint-dark); }
.chain-node:last-child { border-color: var(--navy); }
.chain-node::after { content: '↓'; display: block; font-weight: 400; color: var(--ink-soft); margin-top: 2px; }
.chain-node:last-child::after { content: ''; }
@keyframes chainpulse {
  0%, 100% { box-shadow: none; }
  8%, 20% { box-shadow: 0 0 0 4px rgba(0, 255, 171, 0.18); border-color: var(--mint-dark); }
}
/* Símbolo CTD de fondo en el hero */
.land-hero::before {
  content: 'CTD'; position: absolute; right: -2%; bottom: -6%;
  font-size: clamp(120px, 26vw, 300px); font-weight: 800; line-height: 1;
  color: transparent; -webkit-text-stroke: 1px rgba(0, 255, 171, 0.14);
  pointer-events: none;
}
.steps { list-style: none; margin: 16px 0; padding: 0; display: grid; gap: 12px; }
.steps li { display: flex; gap: 12px; align-items: flex-start; }
.step-n { width: 34px; height: 34px; flex: none; border-radius: 50%; background: var(--navy); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 800; }
.land-foot { text-align: center; padding: 32px 20px 120px; }
@media (min-width: 860px) {
  .land-inner { grid-template-columns: 1.1fr 0.9fr; align-items: center; }
}
/* Modo lite / reduced-motion: todo estático */
[data-perf='lite'] .marquee-track, [data-perf='lite'] .phone, [data-perf='lite'] .land-hero .glow-line, [data-perf='lite'] .chain-node, [data-perf='lite'] .tick { animation: none; }
@media (prefers-reduced-motion: reduce) {
  .marquee-track, .phone, .land-hero .glow-line, .reveal, .chain-node, .tick { animation: none !important; transition: none !important; }
  .reveal { opacity: 1; transform: none; }
}
</style>
