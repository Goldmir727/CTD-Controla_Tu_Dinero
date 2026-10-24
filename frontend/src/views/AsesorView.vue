<template>
  <main class="page asesor">
    <p class="eyebrow">ASESOR IA · PRO</p>

    <!-- Lista de conversaciones -->
    <template v-if="!chatId">
      <div class="cab">
        <h2>Pregunta con tus números</h2>
        <button class="btn-mint" @click="nuevoChat"><i class="bi bi-plus-lg"></i> Nuevo</button>
      </div>
      <p class="sub intro">
        Responde con tu balance, presupuestos y metas. Orientación informativa, no asesoría financiera.
      </p>

      <section v-if="chats.length" class="card lista">
        <div class="lista-cab">
          <strong>Tus conversaciones</strong>
          <span class="sub">{{ chats.length }}</span>
        </div>
        <!-- Antes esto eran chips en una fila que se cortaban a media palabra.
             Una lista deja leer el título completo, la fecha y cuántos mensajes
             tiene, que es lo que se busca al volver a un chat viejo. -->
        <button v-for="c in chats" :key="c.id" class="fila" @click="abrirChat(c.id)">
          <span class="icono"><i class="bi bi-chat-left-text"></i></span>
          <span class="quien">
            <span class="titulo">{{ c.titulo }}</span>
            <small>{{ fechaChat(c.created_at) }} · {{ c.mensajes }} {{ c.mensajes === 1 ? 'mensaje' : 'mensajes' }}</small>
          </span>
          <i class="bi bi-chevron-right flecha"></i>
        </button>
      </section>

      <section v-else class="card vacio">
        <span class="icono grande"><i class="bi bi-chat-square-dots"></i></span>
        <strong>Aún no tienes conversaciones</strong>
        <p class="sub">Pregúntale lo que quieras sobre tu plata. Cada conversación queda guardada aquí para volver cuando quieras.</p>
      </section>

      <p class="sub titulo-sug">Prueba con…</p>
      <div class="sugerencias">
        <button v-for="s in SUGERENCIAS" :key="s" class="sug" @click="usarSugerencia(s)">
          <i class="bi bi-arrow-right-short"></i>{{ s }}
        </button>
      </div>
    </template>

    <!-- Conversación abierta -->
    <template v-else>
      <div class="chat-cab">
        <button class="volver" @click="volverALista">
          <i class="bi bi-arrow-left"></i> Conversaciones
        </button>
        <strong class="titulo-chat">{{ tituloActual }}</strong>
        <button class="link borrar" @click="borrarChat">Borrar</button>
      </div>

      <div class="chat" ref="chatBox">
        <div v-for="(m, i) in msgs" :key="i" :class="['burbuja', m.yo ? 'mia' : 'ia']">
          {{ m.texto }}
        </div>
        <div v-if="loading" class="burbuja ia"><span class="spinner"></span></div>
      </div>
    </template>

    <form class="pregunta" @submit.prevent="enviar">
      <input
        ref="inputPregunta"
        v-model="texto"
        placeholder="Escribe tu pregunta…"
        aria-label="Tu pregunta para el asesor"
        class="input"
        maxlength="1000"
      />
      <button class="btn-mint enviar" :disabled="loading || !texto.trim()" aria-label="Enviar pregunta">
        <i class="bi bi-send"></i>
      </button>
    </form>
    <p v-if="error" class="alert" role="alert">{{ error }}</p>
    <p class="sub limite">Límite justo: 20 consultas al día. Tus chats se guardan solo para ti.</p>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { animacionesOff } from '../composables/usePerf'
import api from '../services/api'
import { confirmar } from '../composables/useConfirm'
import { useToast } from '../composables/useToast'
import { locale } from '../utils/formato'

type Chat = { id: string; titulo: string; mensajes: number; created_at: string }

const msgs = ref<{ yo: boolean; texto: string }[]>([])
const chats = ref<Chat[]>([])
const chatId = ref<string | null>(null)
const chatBox = ref<HTMLElement | null>(null)
const inputPregunta = ref<HTMLInputElement | null>(null)
const texto = ref('')
const loading = ref(false)
const error = ref('')
const toast = useToast()

const SUGERENCIAS = [
  '¿Cómo voy este mes?',
  '¿Puedo gastar $200.000 en ocio?',
  '¿Qué meta priorizo?',
]

const tituloActual = computed(() => chats.value.find((c) => c.id === chatId.value)?.titulo ?? 'Conversación')

async function listar() {
  try {
    const { data } = await api.get<Chat[]>('/asesor/chats')
    chats.value = data
  } catch { /* sin historial: sigue funcionando */ }
}

function nuevoChat() {
  chatId.value = null
  msgs.value = []
  error.value = ''
  void nextTick(() => inputPregunta.value?.focus())
}

/** Volver a la lista no borra nada: el chat queda en el historial y se puede
 *  retomar. Antes solo se podía cambiar de chat con los chips de arriba. */
async function volverALista() {
  chatId.value = null
  msgs.value = []
  error.value = ''
  await listar()
}

async function abrirChat(id: string) {
  error.value = ''
  try {
    const { data } = await api.get(`/asesor/chats/${id}`)
    chatId.value = data.id
    msgs.value = data.mensajes
  } catch { error.value = 'No se pudo abrir el chat.' }
}

async function borrarChat() {
  if (!chatId.value) return
  if (!(await confirmar({ titulo: '¿Borrar este chat?', mensaje: 'Se borra la conversación completa. No se puede deshacer.', ok: 'Borrar', peligro: true }))) return
  await api.delete(`/asesor/chats/${chatId.value}`)
  chats.value = chats.value.filter((c) => c.id !== chatId.value)
  toast.mostrar('Chat borrado')
  await volverALista()
}

function usarSugerencia(s: string) {
  texto.value = s
  void nextTick(() => inputPregunta.value?.focus())
}

/** "2026-10-24 13:50:51.643809" -> "Hoy", "Ayer" o "24 oct". */
function fechaChat(iso: string) {
  const [a, m, d] = iso.slice(0, 10).split('-').map(Number)
  if (!a || !m || !d) return ''
  const fecha = new Date(a, m - 1, d)
  const hoy = new Date()
  const dias = Math.round((new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate()).getTime()
    - fecha.getTime()) / 86_400_000)
  if (dias === 0) return 'Hoy'
  if (dias === 1) return 'Ayer'
  return fecha.toLocaleDateString(locale(), { day: 'numeric', month: 'short' })
}

async function enviar() {
  const pregunta = texto.value.trim()
  if (!pregunta || loading.value) return
  error.value = ''
  msgs.value.push({ yo: true, texto: pregunta })
  texto.value = ''
  loading.value = true
  try {
    const { data } = await api.post('/asesor/chat', { mensaje: pregunta, chat_id: chatId.value })
    // Nunca pintar una burbuja en blanco: si el proveedor devuelve vacío,
    // se avisa y se deja la pregunta en el formulario para reintentar.
    const respuesta = (data.respuesta ?? '').toString().trim()
    if (!respuesta) {
      error.value = 'El asesor volvió sin respuesta. Vuelve a intentarlo.'
    } else {
      msgs.value.push({ yo: false, texto: respuesta })
    }
    if (!chatId.value && data.chat_id) {
      chatId.value = data.chat_id
      await listar()
    }
  } catch (e: unknown) {
    const r = (e as { response?: { status?: number; data?: { detail?: string } } }).response
    error.value = r?.status === 429 ? 'Llegaste al límite de hoy. Vuelve mañana.'
      : r?.status === 503 ? 'El asesor aún no está configurado (falta la clave de IA).'
      : (r?.data?.detail ?? 'El asesor falló. Intenta de nuevo.')
    // La pregunta ya se había mostrado: se devuelve al formulario para no perderla.
    msgs.value.pop()
    texto.value = pregunta
  } finally { loading.value = false }
}

onMounted(listar)
watch([msgs, loading], async () => {
  if (!chatId.value) return
  await nextTick()
  chatBox.value?.lastElementChild?.scrollIntoView({
    behavior: animacionesOff() ? 'auto' : 'smooth',
    block: 'end'
  })
})
</script>

<style scoped>
.cab { display: flex; align-items: center; gap: 10px; margin: 4px 0; }
.cab h2 { font-size: 22px; margin: 0; flex: 1; }
.intro { margin: 0 0 14px; max-width: 60ch; }

.lista { padding: 6px 14px; }
.lista-cab { display: flex; align-items: baseline; justify-content: space-between; padding: 10px 2px 6px; }
.lista-cab strong { font-size: 14px; }
.fila {
  display: flex; align-items: center; gap: 10px; width: 100%; text-align: left;
  background: none; border: 0; border-top: 1px solid var(--line); padding: 11px 2px;
  font: inherit; color: inherit; cursor: pointer; min-height: 56px;
}
.fila:first-of-type { border-top: 0; }
.fila:hover .titulo { text-decoration: underline; }
.icono {
  width: 34px; height: 34px; border-radius: 11px; flex: none;
  background: var(--mint-soft); color: var(--mint-text);
  display: inline-flex; align-items: center; justify-content: center;
}
.icono.grande { width: 44px; height: 44px; font-size: 20px; margin: 0 auto 8px; }
.quien { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.titulo {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; line-height: 1.3;
}
.quien small { color: var(--ink-soft); font-size: 12px; }
.flecha { color: var(--ink-soft); font-size: 13px; }

.vacio { text-align: center; padding: 22px 16px; }
.vacio strong { display: block; margin-bottom: 4px; }
.vacio p { margin: 0 auto; max-width: 38ch; }

.titulo-sug { margin: 16px 0 8px; }
.sugerencias { display: grid; gap: 8px; }
.sug {
  display: flex; align-items: center; gap: 6px; text-align: left;
  background: var(--surface); border: 1px solid var(--line); border-radius: 14px;
  padding: 12px 14px; min-height: 44px; font: inherit; font-size: 14px; color: var(--ink);
  cursor: pointer;
}
.sug i { color: var(--mint-text); font-size: 18px; }
.sug:hover { border-color: var(--mint-dark); }

.chat-cab { display: flex; align-items: center; gap: 10px; margin: 2px 0 10px; }
.volver {
  display: inline-flex; align-items: center; gap: 4px; background: none; border: 0;
  color: var(--ink-soft); font: inherit; font-size: 13px; cursor: pointer; padding: 8px 0;
  min-height: 44px;
}
.volver:hover { color: var(--ink); }
.titulo-chat { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; }
.borrar { color: var(--danger-text); font-size: 13px; }

.chat { display: grid; gap: 8px; margin-top: 4px; }
.burbuja { border-radius: 14px; padding: 10px 14px; max-width: 88%; font-size: 15px; line-height: 1.45; white-space: pre-wrap; }
.burbuja.mia { background: var(--navy); color: #fff; justify-self: end; }
.burbuja.ia { background: var(--surface); border: 1px solid var(--line); color: var(--ink); }

.pregunta { display: flex; gap: 8px; margin-top: 14px; }
.pregunta .input { flex: 1; min-width: 0; }
.enviar { flex: none; width: 48px; padding: 0; display: inline-flex; align-items: center; justify-content: center; }
.limite { margin-top: 8px; }

@media (min-width: 1000px) {
  .lista { max-width: 720px; }
  .sugerencias { max-width: 720px; }
  .chat, .pregunta, .chat-cab { max-width: 780px; }
}
</style>
