# Desplegar CTD en Vercel

CTD se despliega como **un solo proyecto de Vercel** con dos servicios (Vercel
Services, beta disponible en todos los planes):

| Servicio | Carpeta | Qué es | Rutas públicas |
|---|---|---|---|
| `web` | `frontend/` | Vue 3 + Vite + PWA | `/` y todo lo demás |
| `api` | `backend/` | FastAPI + Alembic | `/api/*`, `/health`, `/docs`, `/openapi.json` |

Ambos comparten dominio, así que el frontend llama a `/api/v1` sin configurar
`VITE_API_URL` y sin CORS entre dominios.

La configuración vive en `vercel.json` (raíz). No muevas build/output/framework
al nivel superior: con `services` esas claves pertenecen a cada servicio.

---

## 1. Antes de empezar

- Cuenta de Vercel conectada a GitHub.
- Postgres accesible desde internet. **Vercel Functions no tiene base de datos
  local persistente**: el `db` de `docker-compose.yml` no sirve en producción.
  Opciones: Aiven (el actual), Neon, Supabase, etc.
- La URL debe usar el driver de psycopg2 y SSL:

  ```text
  postgresql+psycopg2://usuario:clave@host:puerto/base?sslmode=require
  ```

  Si la contraseña tiene caracteres especiales (`@`, `#`, `%`, `:`), codifícala
  con porcentaje o la URL se parte en el lugar equivocado.

- Un `JWT_SECRET` real de al menos 32 caracteres:

  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```

---

## 2. Importar el proyecto

1. En Vercel: **Add New → Project → Import Git Repository**.
2. Deja **Root Directory** en `./` (la raíz del repo). No selecciones
   `frontend/` ni `backend/`: los servicios se resuelven desde `vercel.json`.
3. Framework Preset: **Other**. En modo Services, Vercel ignora los campos de
   build/output del panel y usa los de `vercel.json`.
4. No configures `VITE_API_URL`. Si existe en el entorno, el build del frontend
   la incrusta y rompe el mismo-origen. Tampoco definas `VITE_BASE`: la app se
   sirve en la raíz del dominio; `VITE_BASE` es solo para GitHub Pages.

El build de `web` ejecuta `npm install` + `npm run build` y publica `dist/`.
El build de `api` instala `backend/requirements.txt`, usa Python 3.12
(`backend/.python-version`) y ejecuta `backend/scripts/vercel_build.py`.

---

## 3. Variables de entorno

Cópialas desde `docs/vercel.env.example`. Como mínimo, para que la app arranque:

| Variable | Obligatoria | Notas |
|---|---|---|
| `DATABASE_URL` | Sí | Postgres externo con `?sslmode=require`. |
| `JWT_SECRET` | Sí | ≥32 caracteres, distinto de los valores de ejemplo. |
| `CORS_ORIGINS` | Recomendada | `https://tu-dominio.vercel.app`. Sin esto quedan los defaults de localhost; como frontend y API comparten dominio, la app igual funciona. |

El resto (`REDIS_URL`, `SMTP_*`, `OPENAI_API_KEY`, `WOMPI_*`, `WHATSAPP_*`,
`PRO_PRECIO_MES`) es opcional: si falta, esa función se desactiva o usa su
fallback y el resto de la app sigue funcionando.

> Configura `DATABASE_URL` y `JWT_SECRET` también en **Preview**. Vercel importa
> la app durante el build y el arranque falla sin secreto; para previews usa una
> base aparte (o una branch de Neon) y deja `RUN_MIGRATIONS=0`.

> En Vercel, `VERCEL`, `VERCEL_ENV` y `VERCEL_URL` las inyecta la plataforma.
> No las definas a mano.

### Variables recomendadas en Vercel

| Variable | Valor | Por qué |
|---|---|---|
| `DB_POOL_SIZE` | `2` | Cada instancia de Function abre su propio pool; Aiven/Neon tienen límite de conexiones. |
| `DB_MAX_OVERFLOW` | `2` | Igual que arriba. |
| `DB_POOL_TIMEOUT` | `10` | Falla rápido en vez de colgar la petición. |
| `VOZ_MAX_BYTES` | `4000000` | Vercel rechaza cuerpos > 4.5 MB antes de llegar a FastAPI. Un audio de 30 s sobra por debajo de 4 MB. |
| `SMTP_PORT` | `587` | Vercel bloquea el puerto 25; 465 y 587 funcionan. |

### Redis (opcional)

Sin `REDIS_URL`, los códigos 2FA y de recuperación se guardan en Postgres y el
rate-limit sigue en memoria. Es suficiente para el MVP. Si quieres Redis, usa
Upstash desde el Marketplace de Vercel y pega la URL `rediss://...` (TLS).

**WhatsApp sí exige Redis** para vincular un número: sin él, `/whatsapp/vincular`
responde 503. El resto del bot queda apagado si no hay credenciales.

### IA (asesor + captura + voz)

| Variable | Ejemplo |
|---|---|
| `OPENAI_API_KEY` | `gsk_...` (Groq) o `sk-...` (OpenAI) |
| `ASESOR_BASE_URL` | `https://api.groq.com/openai/v1` |
| `ASESOR_MODEL` | `openai/gpt-oss-20b` |
| `VOZ_MODEL` | `whisper-large-v3-turbo` |

No bajes `ASESOR_REASONING_EFFORT` a `low` para captura: medido, se equivoca en
método de pago y categoría. El default del proyecto ya es el correcto.

### Wompi

| Variable | Dónde sale |
|---|---|
| `WOMPI_PUBLIC_KEY` | Dashboard de Wompi |
| `WOMPI_EVENTS_SECRET` | “Secretos para integración técnica” |
| `WOMPI_ENLACE_PRO` | Enlace de pago recurrente del plan PRO |
| `PRO_PRECIO_MES` | Solo se muestra; el cobro real lo hace Wompi |

Webhook de producción:

```text
https://TU-DOMINIO/api/v1/billing/webhook
```

Sin `WOMPI_EVENTS_SECRET` el webhook no puede validar la firma y el cobro queda
deshabilitado. No lo dejes vacío en producción.

### WhatsApp (Meta Cloud API)

| Variable | Dónde sale |
|---|---|
| `WHATSAPP_TOKEN` | Token permanente de la app de Meta |
| `WHATSAPP_PHONE_ID` | ID del número en Meta |
| `WHATSAPP_VERIFY_TOKEN` | El que tú inventas y pegas en Meta |
| `WHATSAPP_APP_SECRET` | App Secret de Meta (firma `X-Hub-Signature-256`) |

Webhook de producción:

```text
https://TU-DOMINIO/api/v1/whatsapp/webhook
```

El código está dormido hasta que existan credenciales; no hace falta configurar
nada para desplegar.

---

## 4. Migraciones

`backend/scripts/vercel_build.py` aplica `alembic upgrade head` **solo** cuando:

- `VERCEL_ENV=production`, o
- `RUN_MIGRATIONS=1`.

Un Preview **no migra** por defecto. Eso evita que una rama en revisión altere
la base real. Si necesitas probar una migración en Preview, apunta
`DATABASE_URL` a una base exclusiva de preview (por ejemplo, una branch de Neon)
y define `RUN_MIGRATIONS=1` solo en ese entorno.

Si el build de producción no puede migrar, el despliegue falla y la versión
anterior sigue sirviendo. Es intencional: mejor un deploy rojo que una API con
el esquema viejo.

---

## 5. Verificar el despliegue

Con el dominio asignado:

| URL | Respuesta esperada |
|---|---|
| `/` | La app (HTML de Vite) |
| `/movimientos` (deep link) | La app, no 404 |
| `/sw.js` | Service worker, `Cache-Control: max-age=0` |
| `/manifest.webmanifest` | Manifest de la PWA |
| `/health` | `{"status":"ok"}` |
| `/api/v1/health` | `{"db":"ok"}` |
| `/docs` | Swagger UI |

Si `/api/v1/health` devuelve `{"db":"error"}`, el problema es la conexión a
Postgres (DNS, SSL, credenciales o límite de conexiones), no el routing.

Prueba también en el celular: instalar la PWA, cerrar sesión de red y verificar
que el aviso offline aparece y que los movimientos se guardan en el dispositivo.

---

## 6. Límites de Vercel que conviene tener presentes

- **Cuerpo de la petición: 4.5 MB.** Afecta audio de voz y, en teoría, importar
  Excel. Un audio de 30 s en Opus pesa mucho menos; aun así el tope de la app
  debe quedar por debajo (ver `VOZ_MAX_BYTES`).
- **Duración máxima: 300 s** en Hobby/Fluid. La transcripción tiene timeout de
  90 s y el asesor de 45 s, así que sobra.
- **Sin sistema de archivos persistente.** Los avatares ya se guardan como
  data-URL en Postgres; no subas archivos a `/tmp` esperando que sobrevivan.
- **SMTP solo en 465/587.** El puerto 25 está bloqueado.
- **Rate-limit en memoria por instancia.** Con varias instancias, el límite de
  login no es global. Para el MVP es aceptable; si crece, moverlo a Redis.
- **Conexiones a Postgres.** Cada instancia abre hasta
  `DB_POOL_SIZE + DB_MAX_OVERFLOW` conexiones. No subas esos valores sin mirar
  el plan de tu base.

---

## 7. Webhooks y dominio final

1. Asigna el dominio definitivo en **Settings → Domains**.
2. Actualiza `CORS_ORIGINS` con ese dominio y redeploy.
3. Configura los webhooks de Wompi y Meta con el dominio final (no con la URL
   efímera de preview).
4. Si cambias `JWT_SECRET`, todas las sesiones se invalidan: los usuarios
   tendrán que volver a entrar.

---

## 8. Rollback

Vercel conserva los deployments anteriores. Desde **Deployments → … →
Promote to Production** vuelves a la versión anterior sin recompilar.

Ojo: las migraciones de Alembic no se revierten solas. Si el deploy nuevo migró
el esquema y vuelves al código viejo, revisa si esa migración es compatible hacia
atrás. Para cambios destructivos, haz la migración en dos pasos (agregar,
desplegar, limpiar después).

---

## 9. Si Services no está disponible para tu cuenta

Vercel Services está en beta y puede no aparecer en algunas cuentas/equipos.
Alternativa: dos proyectos separados.

- **Proyecto frontend**: Root Directory `frontend/`, framework Vite, variable
  `VITE_API_URL=https://tu-api.vercel.app/api/v1`.
- **Proyecto API**: Root Directory `backend/`, framework FastAPI, todas las
  variables del backend y el build command
  `python scripts/vercel_build.py`.

En ese caso, el `vercel.json` de la raíz no se usa: cada proyecto necesita su
propia configuración (el frontend, un rewrite SPA a `/index.html`; el backend,
su build command). No mezcles los dos modelos.

---

## 10. Problemas comunes

| Síntoma | Causa probable |
|---|---|
| El build de API falla con `could not translate host name` | `DATABASE_URL` apunta a un host que no resuelve o la base está apagada. |
| `JWT_SECRET tiene N caracteres; mínimo 32` | El secreto es corto o es uno de los valores de ejemplo. |
| `too many connections` | Baja `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` o usa el connection pooler de tu proveedor. |
| El login devuelve 429 a todos | Rate-limit en memoria compartido por instancia; revisa que `X-Forwarded-For` llegue (Vercel lo agrega). |
| 413 al subir audio | El cuerpo supera 4.5 MB: baja `VOZ_MAX_BYTES` o acorta el audio. |
| La PWA sigue mostrando la versión vieja | `sw.js` debe servirse con `max-age=0`; los headers ya están en `vercel.json`. Fuerza recarga o borra datos del sitio. |
| `/api/v1/health` responde `db: error` | Credenciales/SSL/DNS, no routing. Revisa los logs de la Function. |
| WhatsApp responde 503 al vincular | Falta `REDIS_URL`; el vínculo por PIN lo necesita. |
| El correo 2FA no llega | `SMTP_*` incompleto, contraseña de aplicación incorrecta o límite de Gmail. Revisa los logs. |
