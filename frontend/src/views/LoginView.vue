<template>
<div class="auth-wrap">
  <main class="page rise auth-pc">
    <aside class="auth-brand">
      <p class="eyebrow" style="color: var(--mint)">CTD · CONTROLA TU DINERO</p>
      <h1 class="display">Registra. Analiza.<br />Decide. <span style="color: var(--mint)">Avanza.</span></h1>
      <p class="sub auth-brand-sub">Una sola vista para saber cuanto entra, cuanto sale y que hacer con la quincena.</p>
      <ul class="auth-brand-list">
        <li>Registra ingresos y gastos en segundos.</li>
        <li>Detecta tus fijos y alertas de ritmo.</li>
        <li>Tus datos son tuyos: exportables cuando quieras.</li>
      </ul>
    </aside>

    <section class="auth-form">
      <div style="display: flex; justify-content: flex-end">
        <button type="button" class="theme-toggle" @click="toggleTema" :aria-label="oscuro ? 'Modo claro' : 'Modo oscuro'">
          <i :class="['bi', oscuro ? 'bi-sun' : 'bi-moon']"></i>
        </button>
      </div>
      <div style="text-align: center; margin: 8px 0 8px">
        <Logo :width="72" />
        <h2 style="margin: 12px 0 4px">Bienvenido a CTD</h2>
        <p class="sub">Controla tu dinero con mayor claridad.</p>
      </div>
      <form @submit.prevent="login" style="display: grid; gap: 12px">
        <div class="field">
          <label for="correo">Correo electrónico</label>
          <input id="correo" v-model="correo" type="email" placeholder="tucorreo@gmail.com" class="input" required />
        </div>
        <div class="field">
          <label for="pass">Contraseña</label>
          <div class="pass-wrap">
            <input id="pass" v-model="password" :type="ver ? 'text' : 'password'" placeholder="••••••••" class="input" required />
            <button type="button" class="pass-eye" @click="ver = !ver" aria-label="Mostrar contraseña"><i :class="['bi', ver ? 'bi-eye-slash' : 'bi-eye']"></i></button>
          </div>
        </div>
        <button class="btn-primary" :disabled="loading">{{ loading ? 'Entrando…' : 'Entrar' }}</button>
        <p v-if="error" class="alert" role="alert" aria-live="assertive">{{ error }}</p>
      </form>
<p class="sub" style="text-align: center; margin-top: 16px">¿Sin cuenta? <a href="#" @click.prevent="$router.push('/registro')">Crear cuenta</a></p>
    </section>
  </main>
</div>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import Logo from '../components/Logo.vue'
import { useTema } from '../composables/useTema'
import api from '../services/api'
import { useAuth } from '../stores/auth'
const router = useRouter()
const auth = useAuth()
const { tema, aplicar } = useTema()
const oscuro = computed(() => tema.value === 'dark')
function toggleTema() { aplicar(oscuro.value ? 'light' : 'dark') }
const correo = ref(''); const password = ref(''); const error = ref('')
const ver = ref(false); const loading = ref(false)
async function login() {
  error.value = ''; loading.value = true
  const email = correo.value.trim().toLowerCase()
  try {
    const { data } = await api.post('/auth/login', { correo: email, password: password.value })
    if (data.requires_2fa) {
      localStorage.setItem('pending_2fa_email', email)
      router.push({ path: '/2fa', query: { correo: email } })
      return
    }
    auth.setTokens(data.access_token, data.refresh_token)
    await auth.entrar(router)
  } catch (err: unknown) {
    const r = (err as { response?: { status?: number; data?: { detail?: string } } }).response
    error.value = r?.status === 422 ? 'Revisa el correo: sin espacios ni mayúsculas.' : (r?.data?.detail ?? 'Credenciales inválidas')
  } finally { loading.value = false }
}
</script>
<style>
.link{background:none;border:0;color:var(--ink-soft)}
/* Movil: una sola columna de 400px, exactamente igual que antes. El panel de
   marca se oculta y el ancho no cambia, asi que el movil no se ve afectado. */
/* `.page.auth-pc` y no `.auth-pc`: tokens.css redefine `.page` dentro de un
   media query a 1000px con la misma especificidad, y segun el orden del bundle
   se llevaba el max-width y el margen. Dos clases ganan siempre. */
.page.auth-pc { max-width: 400px; }
.auth-brand { display: none; }

/* Escritorio: el ancho que se desperdiciaba pasa a ser un panel de marca y el
   formulario se queda con un ancho de lectura comodo a la derecha. */
@media (min-width: 1000px) {
  .page.auth-pc {
    max-width: 1080px; margin: 0 auto;
    display: grid; grid-template-columns: 1fr 420px; gap: 56px;
    align-items: center; min-height: calc(100dvh - 76px);
    padding: 20px 24px;
  }
  .auth-brand { display: block; }
  .auth-brand .display { font-size: clamp(38px, 4vw, 52px); line-height: 1.04; margin: 14px 0; }
  .auth-brand-sub { font-size: 17px; max-width: 40ch; }
  .auth-brand-list { list-style: none; margin: 26px 0 0; padding: 0; display: grid; gap: 12px; }
  .auth-brand-list li { position: relative; padding-left: 30px; font-size: 15px; color: var(--ink-soft); }
  .auth-brand-list li::before {
    content: ''; position: absolute; left: 0; top: 6px;
    width: 18px; height: 18px; border-radius: 50%;
    background: var(--mint-tint); border: 1px solid var(--mint);
  }
  .auth-form { width: 100%; }
}
</style>
