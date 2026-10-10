import axios from 'axios'

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? '/api/v1' })

api.interceptors.request.use((c) => {
  const t = localStorage.getItem('access_token')
  if (t) c.headers.Authorization = `Bearer ${t}`
  // Perfil activo (Personal / Negocio). Va en header para no tocar ninguna URL:
  // el backend lo lee de X-Perfil-Id y aplica el filtro a todas las consultas.
  const p = localStorage.getItem('ctd-perfil')
  if (p) c.headers['X-Perfil-Id'] = p
  return c
})

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    if (err.response?.status === 401 && localStorage.getItem('refresh_token')) {
      try {
        const { data } = await axios.post(`${api.defaults.baseURL}/auth/refresh`, {
          refresh_token: localStorage.getItem('refresh_token')
        })
        // Rotación: el backend emite refresh nuevo en cada uso.
        localStorage.setItem('access_token', data.access_token)
        if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token)
        err.config.headers.Authorization = `Bearer ${data.access_token}`
        return api(err.config)
      } catch {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        // La sesión murió: avisar al store (App.vue limpia y redirige).
        // Antes era location.href (recarga brusca); el evento mantiene la SPA.
        window.dispatchEvent(new CustomEvent('ctd:sesion-cerrada'))
      }
    }
    return Promise.reject(err)
  }
)

export default api
