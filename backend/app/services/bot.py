"""El cerebro del bot: que hacer con cada mensaje que llega por WhatsApp.

No es el motor financiero (ese ya existe y se reusa), es el CAPA DE CONVERSACION.
Ahi esta el trabajo que la PWA no tiene: la PWA Remember porque tiene memoria;
un chat es una lista de mensajes sueltos y el "sí" que confirma un gasto llega
tres minutos despues, como si nada.

Los estados:

  listo                   espera un mensaje normal (una frase de gasto, un comando)
  esperando_confirmacion  hay una propuesta en vuelo; lo que llegue se interpreta
                          como si/no/corregir ANTES que como frase nueva

Por que ese orden importa: si el usuario esta confirmando y escribe "corregir el
monto son 30 mil", tratarlo como una frase nueva gastaria una llamada al modelo
para entender algo que ya entendiamos. Primero se resuelve el estado, y solo si
no aplica se cae a la captura nueva.

Decisiones que no son obvias y conviene no deshacer sin pensar:

- "sí" NO guarda nada si la propuesta tiene un monto deducido y no leido. Ahi se
  pide el monto real. Guardar en silencio una cifra que la IA adivino es como se
  pierde la confianza en el reporte entero.

- La propuesta caduca a las 2 horas. Un "sí" de manana debe confirmar lo de hoy,
  no algo de anteayer que ya no esta en la cabeza de nadie.

- Cualquier otro texto durante la confirmacion se trata como frase NUEVA, no
  como error. Si el usuario se equivoco de ventana, quiere registrar otra cosa y
  no Understand por que le dijimos que no.
"""
import json
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.plan import consumo_captura, consumir_captura, es_pro
from app.models.billing import Suscripcion  # noqa: F401  (registro de planes)
from app.models.finance import Category, Transaction
from app.models.perfil import Perfil
from app.models.user import User
from app.models.whatsapp import WhatsappSesion, WhatsappVinculo
from app.services import captura as cap
from app.services import captura_confirmar as capx
from app.services import asesor_tools
from app.services import whatsapp as wa

# Cuanto espera una propuesta antes de caducar. Ver nota de cabecera.
CADUCA_HORAS = 2

AYUDA = """Soy el bot de CTD. Registra tus gastos escribiéndome o con una nota de voz.

Ejemplos:
• "gasté 25 mil en el almuerzo"
• "me pagaron el sueldo de 2 millones"
• "pagué el arriendo, son 1.2 millones, es el de siempre"
• "y 15 mil en gasolina"

También entiendo preguntas:
• "resumen" — cómo vas
• "puedo gastar 80 mil?"
• "deshacer" — borra lo último que registré

Escríbeme lo que quieras. Nada se guarda sin que lo confirmes."""

MENSAJE_SIN_VINCULO = """Hola 👋 Soy el bot de CTD.

Para usarme tienes que vincular tu número desde la app web:
1. Abre CTD en ctda.app
2. Entra a Ajustes y busca "Vincular WhatsApp"
3. Te doy un código de 6 dígitos, lo pegas ahí y quedamos conectados

Mientras tanto te dejo el menú para que veas cómo funciona."""


# ---------- utilidades ----------


def _ahora() -> datetime:
    return datetime.utcnow()


def _perfil_principal(db: Session, user: User) -> Perfil | None:
    p = db.query(Perfil).filter_by(user_id=user.id, principal=True).first()
    return p or db.query(Perfil).filter_by(user_id=user.id).first()


def _sesion(db: Session, user: User, perfil: Perfil) -> WhatsappSesion:
    """La sesion en curso del usuario, creandola si no existe.

    El perfil se pone al CREAR: `perfil_id` tiene FK contra `perfiles` y es NOT
    NULL, asi que dejar la cadena vacia y llenarla despues revienta el INSERT.
    """
    s = db.query(WhatsappSesion).filter_by(user_id=user.id).order_by(
        WhatsappSesion.actualizado.desc()).first()
    if s is None:
        s = WhatsappSesion(id=str(uuid.uuid4()), user_id=user.id,
                           perfil_id=perfil.id, estado="listo")
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _abrir_sesion(db: Session, user: User, perfil: Perfil) -> WhatsappSesion:
    """Devuelve la sesion en curso.

    NO toca `actualizado` a proposito. Si se refrescara en cada mensaje, la
    caducidad de la propuesta nunca se cumpliria (siempre pareceria nueva) y un
    "si" de manana confirmaria un gasto de ayer. `actualizado` solo se mueve
    cuando cambia el estado, en `_capturar`.
    """
    return _sesion(db, user, perfil)


def _es_respuesta(texto: str) -> bool:
    """limpia y minúscula, sin acentos ni signos, para comparar palabras cortas."""
    import unicodedata

    t = "".join(
        ch for ch in unicodedata.normalize("NFD", (texto or "").lower())
        if unicodedata.category(ch) != "Mn"
    )
    return "".join(ch for ch in t if ch.isalnum() or ch.isspace()).strip()


_SI = {"si", "dale", "ok", "okay", "listo", "claro", "confirmo", "confirmar", "yes", "va"}
_NO = {"no", "nop", "nada", "cancelar", "olvidalo", "dejalo", "error", "mal", "no gracias"}
_NUEVO = {"otro", "otrafijo", "esotro", "noeselmismo"}


def _es(texto: str, opciones: set) -> bool:
    return _es_respuesta(texto) in opciones


def _dinero(v: float) -> str:
    return f"${v:,.0f}".replace(",", ".")


# ---------- render de la propuesta a texto ----------


def _linea_movimiento(i: int, m: dict) -> str:
    signo = "+" if m.get("tipo") == "ingreso" else "−"
    cat = m.get("categoria") or "Sin categoría"
    base = f"{i+1}. {signo} {_dinero(float(m.get('monto') or 0))} · {cat}"
    extra = []
    if m.get("descripcion") and m["descripcion"] != cat:
        extra.append(f'"{m["descripcion"]}"')
    if m.get("metodo"):
        extra.append(m["metodo"])
    if m.get("fijo"):
        extra.append("fijo")
    return base + ("  · " + " · ".join(extra) if extra else "")


def _texto_propuesta(p: dict) -> str:
    ms = p.get("movimientos") or []
    cuerpo = "\n".join(_linea_movimiento(i, m) for i, m in enumerate(ms))
    total = p.get("total") or 0
    cierre = f"\n\nTotal de gastos: {_dinero(float(total))}"
    return f"Entendí esto:\n\n{cuerpo}{cierre}"


def _preguntar_fijos(p: dict) -> str:
    """La pregunta de deteccion, pero en texto. En WhatsApp no hay botones que no
    expiren, asi que se responde escribiendo."""
    lineas = []
    for i, m in enumerate(p.get("movimientos") or []):
        for c in (m.get("coincidencias") or [])[:1]:
            lineas.append(
                f"{i+1}. Puede ser tu \"{c['nombre']}\" de siempre "
                f"({_dinero(float(c['monto']))}, día {c['dia']}). "
                f"Responde \"{i+1} es el mismo\" o \"{i+1} es otro\"."
            )
    return "\n\n".join(lineas)


def _pendientes_de_montos(p: dict) -> list[dict]:
    return [m for m in (p.get("movimientos") or []) if m.get("requiere_confirmacion_monto")]


# ---------- comandos ----------


def _resolver_similares(db: Session, captura_id: str, movimiento_ix: int,
                        es_el_mismo: bool, es_nuevo: bool) -> None:
    """Marca la eleccion del usuario sobre una coincidencia de fijo.

    Se guarda DENTRO del registro de la captura, no en la propuesta en memoria,
    porque la propuesta se vuelve a leer cuando llega el "sí" (puede ser otro
    mensaje, otro dia).
    """
    from app.models.captura import Captura

    if not captura_id:
        return
    reg = db.query(Captura).filter_by(id=captura_id).first()
    if not reg:
        return
    props = json.loads(reg.propuestos or "[]")
    for m in props:
        if m.get("ix") != movimiento_ix:
            continue
        c = (m.get("coincidencias") or [{}])[0]
        if es_el_mismo and c.get("id"):
            m["recurrente_id"] = c["id"]
            m["nuevo_fijo"] = False
        elif es_nuevo:
            m["recurrente_id"] = None
            m["nuevo_fijo"] = True
    reg.propuestos = json.dumps(props, default=str)
    db.commit()


def _clave_bot(captura_id: str) -> str:
    """Marca los movimientos que creo el bot.

    Va en `idempotency_key`, que es String(36): "wa" + el uuid sin guiones son 34
    caracteres y caben. Se usa para dos cosas a la vez: que un "sí" repetido no
    duplique el gasto, y para que "deshacer" solo alcance a lo que se registro
    por aqui.
    """
    return ("wa" + str(captura_id).replace("-", ""))[:36]


def _deshacer(db: Session, user: User, perfil: Perfil) -> str:
    """Borra lo ultimo que se registro POR EL BOT en este perfil.

    Dos decisiones que no son obvias:

    - No se apoya en `Transaction.fecha`: registrar hoy un movimiento de hace
      tres meses pondria esa fila como "la ultima" y el deshacer se llevaria
      otra cosa. El orden es por `created_at`.

    - Solo toca filas con clave de bot. Si el usuario escribio algo en la web hace
      un rato, que el bot le borre eso al decir "deshacer" seria peor que no
      tener la funcion.

    Sin esto, un "me equivoque, eran 5 mil no 50" no tendria arreglo y el usuario
    tendria que entrar a la web.
    """
    from app.models.captura import Captura

    reg = db.query(Captura).filter_by(user_id=user.id, perfil_id=perfil.id,
                                      estado="guardado").order_by(
        Captura.created_at.desc()).first()
    if reg is None:
        return "No encontré nada registrado por aquí para deshacer."
    clave = _clave_bot(reg.id)
    borrados = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.idempotency_key == clave,
    ).delete(synchronize_session=False)
    if not borrados:
        return "Ese registro no lo puedo deshacer desde aquí. Hazlo en la web."
    reg.estado = "deshecho"
    db.commit()
    plural = "s" if borrados != 1 else ""
    return f"Listo, borré {borrados} movimiento{plural}."


def _consulta_pendiente(texto: str) -> bool:
    """True si parece una pregunta al asesor y no una frase de gasto."""
    t = _es_respuesta(texto)
    return t in ("resumen", "comovoy", "comoestoy") or t.startswith("puedogastar")


def _responder_asesor(db: Session, user: User, perfil: Perfil, texto: str) -> str:
    """Ejecuta una pregunta con las herramientas del asesor.

    No se mete al chat completo (que guarda historial y es mas caro): aqui se
    resuelve con las herramientas y ya. Si la pregunta es ambigua, el bot pide
    que lareated a la app, donde si hay historial.
    """
    t = _es_respuesta(texto)
    try:
        if t.startswith("puedogastar"):
            import re

            m = re.search(r"([\d.]+)", texto.replace(",", ""))
            if not m:
                return "¿Cuánto quieres gastar? Ej: \"puedo gastar 80 mil?\""
            monto = float(m.group(1).replace(".", ""))
            if monto > 1_000_000:  # "80 mil" llega como 80; "800 mil" como 800
                monto *= 1000
            r = asesor_tools.ejecutar("puedo_gastar", {"monto": monto}, db,
                                      user.id, perfil.id)
            return _texto_puedo_gastar(r, monto)
        r = asesor_tools.ejecutar("resumen_financiero", {}, db, user.id, perfil.id)
        return _texto_resumen(r)
    except Exception as e:  # noqa: BLE001 - al usuario no le sirven las traces
        return f"No pude calcular eso ahora mismo: {str(e)[:120]}"


def _texto_puedo_gastar(r: dict, monto: float) -> str:
    if not isinstance(r, dict):
        return "No pude calcular eso."
    # Las claves exactas las decide asesor_tools; se leen defensivamente para
    # que un rename ahi no rompa el bot entero.
    for clave in ("puede", "queda", "maximo"):
        if clave in r and isinstance(r[clave], (int, float, bool)):
            if r[clave]:
                return f"Sí te alcanza: {_dinero(float(r[clave]))} es tu tope cómodo para no quedarte sin nada."
    return f"Con {_dinero(monto)} estás dentro de tu margen según los últimos meses."


def _texto_resumen(r: dict) -> str:
    if not isinstance(r, dict):
        return "No pude Armar el resumen ahora mismo."
    lineas = ["Here's cómo vas 📊"]
    for clave, etiqueta in (("ingresos", "Entradas"), ("gastos", "Gastos"),
                            ("balance", "Balance")):
        if isinstance(r.get(clave), (int, float)):
            lineas.append(f"{etiqueta}: {_dinero(float(r[clave]))}")
    if len(lineas) == 1:
        return "Todavía no tengo suficientes movimientos para armarte el resumen. Registra uno y vuelvo a mirar."
    return "\n".join(lineas)


# ---------- la maquina de estados ----------


def procesar(db: Session, telefono: str, texto: str, audio_id: str | None = None) -> str:
    """Devuelve el texto a responder. NUNCA lanza: un error acá se traduce en un
    500 que hace que Meta reintente el mismo mensaje para siempre."""
    vinculo = db.query(WhatsappVinculo).filter_by(telefono=telefono, activo=True).first()
    if vinculo is None:
        return MENSAJE_SIN_VINCULO
    user = db.get(User, vinculo.user_id)
    if user is None or not user.onboarding_done:
        return ("Veo tu número pero tu cuenta de CTD todavía no está lista. "
                "Abre la app, completa el onboarding y vuelve a escribirme.")
    perfil = _perfil_principal(db, user)
    if perfil is None:
        return "Tu cuenta no tiene ningún perfil todavía. Créalo desde la app."

    # Nota de voz -> texto. Se transcribe con el mismo Whisper que la web.
    transcripcion = None
    if audio_id:
        try:
            audio, mime = wa.descargar_audio(audio_id)
            texto = cap.transcribir(audio, "nota.ogg", mime)
            transcripcion = "whatsapp"
        except Exception:  # noqa: BLE001
            return "No pude escuchar esa nota de voz 🙉 ¿Me lo escribes?"

    texto = (texto or "").strip()
    if not texto:
        return "¿Me cuentas qué registras?"

    # Cuota ANTES de gastar nada: el bot no puede ser una puerta abierta a la
    # clave de la IA.
    try:
        consumir_captura(db, user)
    except Exception:  # 429 de cuota
        cfg = consumo_captura(db, user)
        if es_pro(user):
            return "Ahora mismo no pude responder. Intenta en un momento."
        return (f"Llegaste al límite de {cfg['limite']} capturas por hoy. "
                "Se reinicia mañana. En la app web no hay límite.")

    ses = _abrir_sesion(db, user, perfil)

    # Comandos globales: funcionan con una propuesta en vuelo.
    t = _es_respuesta(texto)
    if t in ("ayuda", "menu", "inicio", "hola", "holi"):
        return AYUDA
    if t == "deshacer":
        return _deshacer(db, user, perfil)

    # Estado: hay algo esperando confirmacion.
    if ses.estado == "esperando_confirmacion":
        return _resolver_confirmacion(db, user, perfil, ses, texto, t)

    # Preguntas al asesor.
    if _consulta_pendiente(texto):
        return _responder_asesor(db, user, perfil, texto)

    # Cualquier otra cosa es una captura.
    return _capturar(db, user, perfil, ses, texto, transcripcion)


def _resolver_confirmacion(db: Session, user: User, perfil: Perfil,
                           ses: WhatsappSesion, texto: str, t: str) -> str:
    if (ses.actualizado and (_ahora() - ses.actualizado).total_seconds() > CADUCA_HORAS * 3600):
        ses.estado = "listo"
        ses.captura_id = None
        db.commit()
        return "Se me pasó la propuesta anterior. ¿Me la repites?"

    propuesta = _cargar_propuesta(db, ses.captura_id)

    if _es(texto, _SI):
        dudosos = _pendientes_de_montos(propuesta) if propuesta else []
        if dudosos:
            return ("Antes de guardar necesito que me confirmes el monto: "
                    + ", ".join(f"{i+1}) {_dinero(float(m.get('monto') or 0))}"
                                for i, m in enumerate(dudosos))
                    + ". Escríbelo como \"1 es 30000\".")
        return _guardar(db, user, perfil, ses, propuesta)

    if _es(texto, _NO):
        ses.estado = "listo"
        ses.captura_id = None
        db.commit()
        return "Listo, no guardé nada."

    # "1 es el mismo" / "1 es otro"
    if "esmismo" in t.replace(" ", "") or t.endswith("esmismo"):
        return _marcar_similar(db, ses, texto, es_el_mismo=True)
    if "esotro" in t.replace(" ", "") or t in _NUEVO:
        return _marcar_similar(db, ses, texto, es_el_mismo=False)

    # No era ninguno de esos: el usuario quiere registrar otra cosa. Se trata
    # como frase nueva y se cambia la captura en vuelo.
    ses.estado = "listo"
    db.commit()
    return _capturar(db, user, perfil, ses, texto, None)


def _marcar_similar(db: Session, ses: WhatsappSesion, texto: str, es_el_mismo: bool) -> str:
    import re

    nums = re.findall(r"\d+", texto)
    if not nums:
        return "¿Sobre cuál? Escríbelo como \"1 es el mismo\"."
    ix = int(nums[0]) - 1
    _resolver_similares(db, ses.captura_id, ix, es_el_mismo, not es_el_mismo)
    return ("Anotado." + (" Lo enlacé con tu fijo de siempre."
                          if es_el_mismo else " Lo dejo como un fijo nuevo.")
            + " Cuando quieras, responde \"sí\" para guardar.")


def _cargar_propuesta(db: Session, captura_id: str | None) -> dict:
    from app.models.captura import Captura

    if not captura_id:
        return {}
    reg = db.query(Captura).filter_by(id=captura_id).first()
    if not reg:
        return {}
    import json as _json

    try:
        movimientos = _json.loads(reg.propuestos or "[]")
    except ValueError:
        return {}
    return {"movimientos": movimientos, "captura_id": captura_id,
            "total": sum(float(m.get("monto") or 0) for m in movimientos
                         if m.get("tipo") == "gasto")}


def _guardar(db: Session, user: User, perfil: Perfil,
             ses: WhatsappSesion, propuesta: dict) -> str:
    movimientos = propuesta.get("movimientos") or []
    if not movimientos:
        ses.estado = "listo"
        db.commit()
        return "Ya no tengo esa propuesta guardada. ¿Me la repites?"
    try:
        r = capx.confirmar_captura(db, user, perfil, propuesta["captura_id"], movimientos,
                                    _clave_bot(propuesta["captura_id"]))
    except ValueError as e:
        return f"No pude guardar: {e}. Revísalo en la app."
    ses.estado = "listo"
    ses.captura_id = None
    db.commit()
    if r.get("ya_guardada"):
        return "Ese movimiento ya estaba guardado."
    if r["errores"]:
        return (f"Guardé {r['creados']}, pero {len(r['errores'])} no se pudieron: "
                f"{r['errores'][0]['detalle']}")
    total = sum(float(g["monto"]) for g in r["guardados"] if g["tipo"] == "gasto")
    plural = "movimiento" if r["creados"] == 1 else "movimientos"
    extra = f" Total {_dinero(total)}." if total else ""
    return f"✅ Guardé {r['creados']} {plural}.{extra}"


def _capturar(db: Session, user: User, perfil: Perfil, ses: WhatsappSesion,
              texto: str, transcripcion: str | None) -> str:
    try:
        propuesta = capx.proponer(db, user, perfil, texto, transcripcion)
    except cap.CapturaError as e:
        return str(e)
    except Exception as e:  # noqa: BLE001
        return f"No pude analizar eso: {str(e)[:140]}"

    ses.estado = "esperando_confirmacion"
    ses.captura_id = propuesta["captura_id"]
    ses.propuestos = json.dumps(propuesta.get("movimientos"), default=str)
    ses.actualizado = _ahora()
    db.commit()

    cuerpo = _texto_propuesta(propuesta)
    extras = []
    if propuesta.get("sin_cuenta"):
        extras.append("⚠ No tienes cuentas creadas. Abre la app y crea una para que esto se guarde bien.")
    fijos = _preguntar_fijos(propuesta)
    if fijos:
        extras.append(fijos)
    if propuesta.get("avisos"):
        extras.extend(str(a) for a in propuesta["avisos"])
    if extras:
        cuerpo += "\n\n" + "\n\n".join(extras)
    return cuerpo + "\n\n¿Lo guardo? Responde *sí* o *no*."