<template>
  <div class="auth-wrap">
    <main class="page rise" style="max-width: 400px">
      <div style="display: flex; justify-content: flex-end">
        <button type="button" class="theme-toggle" @click="toggleTema" :aria-label="oscuro ? 'Modo claro' : 'Modo oscuro'">
          <i :class="['bi', oscuro ? 'bi-sun' : 'bi-moon']"></i>
        </button>
      </div>
      <div style="text-align: center; margin: 8px 0 8px">
        <Logo :width="72" />
        <h2 style="margin: 12px 0 4px">Crear cuenta</h2>
        <p class="sub">Controla tu dinero con mayor claridad.</p>
      </div>
      <div style="text-align: center">
        <img v-if="f.foto" :src="f.foto" alt="Tu foto" class="avatar-lg" />
        <i v-else class="bi bi-person-circle" style="font-size: 64px; color: var(--ink-soft)"></i>
        <div><button type="button" class="link" @click="fotoInput?.click()">{{ f.foto ? 'Cambiar foto' : 'Agregar foto (opcional)' }}</button></div>
        <input ref="fotoInput" type="file" accept="image/*" hidden @change="elegirFoto" />
        <p v-if="eFoto" class="alert">{{ eFoto }}</p>
      </div>
      <form @submit.prevent="go" style="display: grid; gap: 12px">
        <div class="field">
          <label for="nombre">Nombre</label>
          <input id="nombre" v-model="f.nombre" placeholder="Johan" class="input" required />
        </div>
        <div class="field">
          <label for="correo">Correo electrónico</label>
          <input id="correo" v-model="f.correo" type="email" placeholder="Gmail para 2FA" class="input" required />
        </div>
        <div class="field">
          <label for="pass">Contraseña</label>
          <div class="pass-wrap">
            <input id="pass" v-model="f.password" :type="ver ? 'text' : 'password'" minlength="8" placeholder="Mínimo 8 caracteres" class="input" required />
            <button type="button" class="pass-eye" @click="ver = !ver" aria-label="Mostrar contraseña"><i :class="['bi', ver ? 'bi-eye-slash' : 'bi-eye']"></i></button>
          </div>
        </div>
        <div class="field">
          <label for="moneda">Moneda</label>
          <select id="moneda" v-model="f.moneda" class="input"><option>COP</option><option>USD</option><option>MXN</option><option>EUR</option></select>
        </div>
        <label class="check"><input type="checkbox" v-model="f.t" /> Acepto los <a href="#" @click.prevent="$router.push('/terminos')">Términos y Condiciones</a></label>
        <label class="check"><input type="checkbox" v-model="f.d" /> Acepto la <a href="#" @click.prevent="$router.push('/datos')">Política de Tratamiento de Datos</a> (Ley 1581 de 2012)</label>
        <button class="btn-primary" :disabled="loading || !f.t || !f.d">{{ loading ? 'Creando…' : 'Crear y continuar' }}</button>
        <p v-if="e" class="alert">{{ e }}</p>
      </form>
      <p class="sub" style="text-align: center; margin-top: 16px">¿Ya tienes cuenta? <a href="#" @click.prevent="$router.push('/login')">Iniciar sesión</a></p>
    </main>
  </div>
</template>
<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import Logo from '../components/Logo.vue'
import { useTema } from '../composables/useTema'
import { archivoADataURL } from '../composables/useFoto'
import api from '../services/api'
import { useAuth } from '../stores/auth'
const { tema, aplicar } = useTema()
const oscuro = computed(() => tema.value === 'dark')
function toggleTema() { aplicar(oscuro.value ? 'light' : 'dark') }
const router = useRouter()
const auth = useAuth()
const f = reactive({ nombre: '', correo: '', password: '', moneda: 'COP', foto: null as string | null, t: false, d: false })
const e = ref('')
const eFoto = ref('')
const fotoInput = ref<HTMLInputElement | null>(null)
const ver = ref(false); const loading = ref(false)
async function elegirFoto(ev: Event) {
  eFoto.value = ''
  const file = (ev.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    const url = await archivoADataURL(file)
    if (url.length > 300_000) { eFoto.value = 'Foto muy pesada.'; return }
    f.foto = url
  } catch { eFoto.value = 'No se pudo leer la imagen.' }
}
async function go() {
  e.value = ''; loading.value = true
  f.correo = f.correo.trim().toLowerCase()
  try {
    await api.post('/auth/registro', { nombre: f.nombre, correo: f.correo, password: f.password, moneda: f.moneda, foto_url: f.foto, acepta_terminos: f.t, acepta_datos: f.d })
    const { data } = await api.post('/auth/login', { correo: f.correo, password: f.password })
    auth.setTokens(data.access_token, data.refresh_token)
    auth.setOnboarding(false)
    router.push('/onboarding')
  } catch { e.value = 'Ese correo ya existe o datos inválidos (422).' }
  finally { loading.value = false }
}
</script>
<style>.check{display:flex;gap:8px;align-items:flex-start;font-size:13px;color:var(--ink-soft)}.check input{margin-top:3px;accent-color:var(--mint-dark)}
.avatar-lg{width:96px;height:96px;object-fit:cover;border-radius:50%;border:2px solid var(--mint)}</style>
