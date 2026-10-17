import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', component: () => import('../views/LandingView.vue') },
    { path: '/cookies', component: () => import('../views/CookiesView.vue') },
    { path: '/terminos', component: () => import('../views/TerminosView.vue') },
    { path: '/datos', component: () => import('../views/DatosView.vue') },
    { path: '/login', component: () => import('../views/LoginView.vue') },
    { path: '/registro', component: () => import('../views/RegistroView.vue') },
    { path: '/onboarding', component: () => import('../views/OnboardingView.vue') },
    { path: '/2fa', component: () => import('../views/TwoFaView.vue') },
    { path: '/inicio', component: () => import('../views/DashboardView.vue') },
    { path: '/movimientos', component: () => import('../views/MovimientosView.vue') },
    { path: '/movimientos/nuevo', component: () => import('../views/NuevoMovimientoView.vue') },
    { path: '/plan', component: () => import('../views/PlanView.vue') },
    { path: '/analisis', component: () => import('../views/AnalisisView.vue') },
    { path: '/asesor', component: () => import('../views/AsesorView.vue') },
    { path: '/pro', component: () => import('../views/ProView.vue') },
  { path: '/config', component: () => import('../views/ConfigView.vue') }
  ]
})

router.beforeEach((to) => {
  const pub = ['/', '/cookies', '/terminos', '/datos', '/login', '/registro', '/2fa']
  if (!pub.includes(to.path) && !localStorage.getItem('access_token')) return '/login'
  // Onboarding de una sola vez: si ya está hecho, no se puede repetir
  if (to.path === '/onboarding' && localStorage.getItem('ctd-onboarding') === '1') return '/inicio'
})

export default router
