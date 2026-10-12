<template>
  <main class="page">
    <div class="eyebrow">ASESOR IA · PRO</div>
    <div style="display: flex; gap: 8px; align-items: center">
      <h2 style="margin: 4px 0; flex: 1">Pregunta con tus números</h2>
      <button class="btn-mint" @click="nuevoChat">+ Nuevo</button>
    </div>
    <p class="sub">Responde con tu balance, presupuestos y metas. Orientación informativa, no asesoría financiera.</p>
    <div v-if="chats.length" style="display: flex; gap: 8px; overflow-x: auto; padding: 4px 0 8px">
      <button v-for="c in chats" :key="c.id" :class="['chip', 'chat-chip', c.id === chatId ? 'on' : '']" @click="abrirChat(c.id)" :title="c.titulo">
        {{ c.titulo }}
      </button>
    </div>
    <div class="chat" ref="chatBox">
      <div v-if="!msgs.length && !loading" class="empty">
        <strong>Prueba con…</strong>
        “¿Cómo voy este mes?” · “¿Puedo gastar $200.000 en ocio?” · “¿Qué meta priorizo?”
      </div>
      <div v-for="(m, i) in msgs" :key="i" :class="['burbuja', m.yo ? 'mia' : 'ia']">
        {{ m.texto }}
        <div v-if="!m.yo && i === msgs.length - 1 && chatId" style="margin-top: 6px">
          <button class="link" style="font-size: 12px" @click="borrarChat">Borrar este chat</button>
        </div>
      </div>
      <div v-if="loading" class="burbuja ia"><span class="spinner"></span></div>
    </div>
    <form @submit.prevent="enviar" style="display: flex; gap: 8px; margin-top: 10px">
      <input v-model="texto" placeholder="Escribe tu pregunta…" class="input" style="flex: 1; min-width: 0" maxlength="1000" />
      <button class="btn-mint" :disabled="loading || !texto.trim()"><i class="bi bi-send"></i></button>
    </form>
    <p v-if="error" class="alert">{{ error }}</p>
    <p class="sub">Límite justo: 20 consultas al día. Tus chats se guardan solo para ti.</p>
  </main>
</template>
<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { animacionesOff } from '../composables/usePerf'
import api from '../services/api'
const msgs = ref<{ yo: boolean; texto: string }[]>([])
const chats = ref<{ id: string; titulo: string }[]>([])
const chatId = ref<string | null>(null)
const chatBox = ref<HTMLElement | null>(null)
const texto = ref('')
const loading = ref(false)
const error = ref('')

async function listar() {
  try {
    const { data } = await api.get('/asesor/chats')
    chats.value = data
  } catch { /* sin historial: sigue funcionando */ }
}
async function nuevoChat() {
  chatId.value = null
  msgs.value = []
  error.value = ''
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
  if (!chatId.value || !confirm('¿Borrar este chat y su historial?')) return
  await api.delete(`/asesor/chats/${chatId.value}`)
  chats.value = chats.value.filter((c) => c.id !== chatId.value)
  await nuevoChat()
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
  await nextTick()
  chatBox.value?.lastElementChild?.scrollIntoView({
    behavior: animacionesOff() ? 'auto' : 'smooth',
    block: 'end'
  })
})
</script>
<style>
.chat { display: grid; gap: 8px; margin-top: 12px; }
.burbuja { border-radius: 14px; padding: 10px 14px; max-width: 88%; font-size: 15px; }
.burbuja.mia { background: var(--navy); color: #fff; justify-self: end; }
.burbuja.ia { background: var(--surface); border: 1px solid var(--line); color: var(--ink); }
/* .chip vive en tokens.css */
.chat-chip{white-space:nowrap;max-width:170px;overflow:hidden;text-overflow:ellipsis;flex:none}
</style>
