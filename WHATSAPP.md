# Bot de WhatsApp — puesta en marcha

El código ya está desplegado y probado, pero **nada funciona hasta que existan
las credenciales de Meta**. Este documento es el camino de ida: son pasos de
Meta, no de código, y hay esperas que no dependen de nosotros.

Alta estimada: **1 a 3 semanas**, y casi todo es espera de aprobación.

---

## 0. Antes de empezar, dos decisiones

**Número dedicado.** El bot necesita un número propio, no tu celular personal.
Si usas el tuyo, cualquier mensaje que llegue te salta como si fuera tuyo y
Meta puede deshabilitarlo. Necesitas un SIM o una línea VoIP nueva.

**HTTPS.** El webhook solo funciona por HTTPS con certificado válido. El
`Caddyfile` ya sirve por TLS en el puerto 8443, pero Meta **no acepta puertos
estándar con IP cruda**: vas a necesitar un dominio (aunque pongas Cloudflare
delante). Sin dominio, este paso se queda atascado.

---

## 1. Cuenta de Meta Business

1. Entrá a <https://business.facebook.com> y creá una cuenta de empresa.
2. Verificá la empresa. Meta pide RUT o equivalente y datos del representante.
   **Esto puede tardar días.**
3. Creá un **Portfolio de Negocio** (Business Portfolio) con tu empresa.

## 2. Crear la app y el producto de WhatsApp

1. Meta for Developers → **Create App** → tipo *Business*.
2. Añadí el producto **WhatsApp**.
3. En WhatsApp → *API Setup* vas a ver:
   - **Phone number ID**
   - **WhatsApp Business Account ID (WABA ID)**
   - Un **token de prueba** que caduca en 24 h (no sirve para producción).
4. En *Configuration → Webhooks*:
   - **Callback URL**: `https://TU_DOMINIO/api/v1/whatsapp/webhook`
   - **Verify token**: inventalo tú. Ejemplo: `ctd-verify-cambia-esto`
   - Suscríbete al evento **`messages`**.

   ⚠️ El botón *Verify* hace un GET con `hub.mode`, `hub.verify_token` y
   `hub.challenge`. Si da verde, el código de `GET /whatsapp/webhook` está bien.

5. En *API Setup → Temporary access token* generá un token **permanente**
   (System User). El token de prueba expira en 24 h y en 24 h el bot deja de
   funcionar sin avisar.

## 3. Número de producción

En WhatsApp → *Phone numbers* → **Add**. Verificá el número por SMS o llamada.
Solo después puedes enviar a alguien que no sea de tu equipo.

## 4. Variables de entorno

Copiá esto a tu `.env` (**no se sube al repo**):

```bash
WHATSAPP_TOKEN=el_token_permanente_del_system_user
WHATSAPP_PHONE_ID=123456789012345
WHATSAPP_VERIFY_TOKEN=ctd-verify-cambia-esto
WHATSAPP_APP_SECRET=el_app_secret_de_tus_app_settings
```

`WHATSAPP_APP_SECRET` **no es opcional**. Sin él el webhook no puede verificar
la firma `X-Hub-Signature-256`, y sin verificación cualquiera que haga un POST a
la URL usaría el bot y gastaría tu cuota de la IA.

## 5. Reiniciar y probar

```bash
docker compose up -d api
docker compose exec -T api python -c "from app.main import app; print('ok')"
```

Prueba de humo (el bot responde a un número SIN vincular, que es lo correcto):

```bash
curl -X POST https://TU_DOMINIO/api/v1/whatsapp/webhook \
  -H "Content-Type: application/json" -d '{}'
# debe devolver {"ok":true}
```

## 6. Vincular tu cuenta

1. Abrí CTD → Ajustes → **Registrar por WhatsApp**.
2. Escribí tu número → *Enviarme un código*.
3. Te llega un PIN de 6 dígitos por el mismo WhatsApp. Pegalo en la app.
4. Escribile al bot: `gasté 25 mil en el almuerzo`.

---

## Límites que conviene conocer antes de prometer nada

| Límite | Valor | Qué implica |
|---|---|---|
| Ventana de 24 h | 24 h desde tu último mensaje | Fuera de eso solo se pueden mandar **plantillas aprobadas**. El bot se calla: no puede avisarte nada por su cuenta. |
| Plantillas | Case aprobación de Meta | Recoger usuarios es lo que rompe la estrategia freemium. Ver más abajo. |
| Conversations (gratis) | ~1000/mes | Suficiente para validar. Para producción hay que pagar. |
| Audio de salida | Requiere plantilla aprobada | El bot responde en texto; mandar nota de voz necesita aprobación aparte. |

**La ventana de 24 h es el límite de verdad del negocio.** El usuario te escribe
(cuentas los 24 h), tú le respondes (24 h renewed), pero al día siguiente no puedes
mandarle "oye, gastaste 80% del presupuesto". Solo con plantilla aprobada. Y las
plantillas las revisa Meta una a una, y rechazan las que suenan a publicidad.

Si vas a construir sobre retención, esa parte se planifica **desde el día uno**,
no después.

---

## Plantilla sugerida

Para reconectar al usuario (fuera de la ventana):

```
Hola {{1}} 👋 Te escribo porque llevas {{2}} días sin registrar nada.
Escríbeme "gasté 25 mil en el almuerzo" y te lo guardo.
Responde SALIR para no recibir más.
```

`SALIR` en mayúsculas es un comando de baja que Meta exige en varios mercados.

---

## Diagnóstico

| Síntoma | Causa probable |
|---|---|
| Meta da 403 al verificar | `WHATSAPP_VERIFY_TOKEN` distinto al configurado en Meta |
| Webhook responde `{"ok":true}` pero el bot no contesta | Falta `WHATSAPP_APP_SECRET` (rechaza la firma en silencio) |
| Contesta a unos y a otros no | Fuera de la ventana de 24 h |
| `131026` en los logs | Plantilla no aprobada |
| 401 al enviar | Token de prueba expiró; genera uno permanente |

---

## Decisión pendiente

**Meta puede cambiar la política, un número puede ser baneado.** Aceptamos ese
riesgo, pero conviene tener un canal de respaldo escrito y barato de montar
(Telegram o SMS) antes de depender del todo de esto. El diseño lo permite: el
cerebro (`services/bot.py`) no sabe nada de WhatsApp, solo recibe texto y
devuelve texto.