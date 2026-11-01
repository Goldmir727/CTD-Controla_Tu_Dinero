import axios from 'axios'

const DEVICE_ID_KEY = 'ctd-device-id'

function obtenerDeviceId(): string {
  if (typeof localStorage === 'undefined') return ''
  let id = localStorage.getItem(DEVICE_ID_KEY)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(DEVICE_ID_KEY, id)
  }
  return id
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/api/v1',
  // Timeout corto: si no hay respuesta en 5s, se asume sin red y se falla rapido
  // para no congelar la app en modo offline.
  timeout: 5000,
})

api.interceptors.request.use((c) => {
  const t = localStorage.getItem('access_token')
  if (t) c.headers.Authorization = `Bearer ${t}`
  const p = localStorage.getItem('ctd-perfil')
  if (p) c.headers['X-Perfil-Id'] = p
  const d = obtenerDeviceId()
  if (d) c.headers['X-Device-Id'] = d
  return c
})

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    // Sin red: no intentar refresh, no tocar tokens. El repositorio usa la copia local.
    if (!navigator.onLine) {
      return Promise.reject(err)
    }

    // 401 con refresh token: intentar rotar solo si hay red.
    if (err.response?.status === 401 && localStorage.getItem('refresh_token')) {
      try {
        const { data } = await axios.post(`${api.defaults.baseURL}/auth/refresh`, {
          refresh_token: localStorage.getItem('refresh_token'),
        })
        localStorage.setItem('access_token', data.access_token)
        if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token)
        err.config.headers.Authorization = `Bearer ${data.access_token}`
        return api(err.config)
      } catch {
        // Refresh falló por red o token invalido: no borrar sesion si estamos offline.
        if (!navigator.onLine) {
          return Promise.reject(err)
        }
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.dispatchEvent(new CustomEvent('ctd:sesion-cerrada'))
      }
    }
    return Promise.reject(err)
  }
)

export default api
