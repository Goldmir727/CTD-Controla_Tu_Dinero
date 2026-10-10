import { VitePWA } from 'vite-plugin-pwa'
import vue from '@vitejs/plugin-vue'
import fs from 'node:fs'
import path from 'node:path'
import { defineConfig } from 'vite'

// HTTPS LAN (celular): usa certs/lan.pem si existe (mkcert). Si no, preview va en http.
const lanCert = path.resolve(__dirname, '../certs/lan.pem')
const lanKey = path.resolve(__dirname, '../certs/lan-key.pem')
const lanHttps =
  fs.existsSync(lanCert) && fs.existsSync(lanKey)
    ? { cert: fs.readFileSync(lanCert), key: fs.readFileSync(lanKey) }
    : undefined

export default defineConfig({
  define: { __APP_VERSION__: JSON.stringify(process.env.npm_package_version ?? '0.0.0') },
  // GitHub Pages (sitio de proyecto): compilar con VITE_BASE=/nombre-repo/
  base: process.env.VITE_BASE ?? '/',
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'CTD - Controla Tu Dinero',
        short_name: 'CTD',
        description: 'Registra. Entiende. Decide. Avanza.',
        theme_color: '#050B3B',
        background_color: '#FFFFFF',
        display: 'standalone',
        start_url: '.',
        scope: '.',
        id: '.',
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' }
        ]
      },
      // globPatterns deja fuera .woff/.woff2 de bootstrap-icons: son 314 kB que se
      // descargan aparte. El precache cubre el shell, no los datos: /api/* NO se
      // cachea a proposito, mostrar saldos viejos es peor que mostrar un error.
      workbox: { globPatterns: ['**/*.{js,css,html,png,ico}'] }
    })
  ],
  build: {
    // El chunk de /analisis pesa ~566 kB (ECharts con dona, barras y lineas) y es
    // lazy: no se descarga hasta que el usuario entra a Datos. Se sube el umbral
    // para que el aviso no tape otros problemas reales de tamaño.
    chunkSizeWarningLimit: 700
  },
  server: { port: 5173, proxy: { '/api': 'http://localhost:8000' } },
  preview: { port: 4173, strictPort: true, host: true, https: lanHttps }
})
