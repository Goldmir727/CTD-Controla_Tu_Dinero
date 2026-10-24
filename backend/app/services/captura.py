"""Captura en lenguaje natural: "gaste 18 mil en el almuerzo y 5 mil en un taxi
con Nequi" -> propuesta de movimientos, lista para que el usuario confirme con un toque.

Por que NO se guarda directo: el modelo se equivoca. Medido, con
reasoning_effort=low respondio "Efectivo" cuando el texto decia "con Nequi", y en
otra prueba invento una categoria ("Taxi") que no existe. Aqui el modelo solo
PROPONE y el backend valida, marca cuanto viene del texto y cuanto se imagino.

Arquitectura en tres capas, de la mas barata a la mas cara:
1. Reglas deterministas (services/colombia.py): slang, montos, fechas, metodo,
   categoria por modismo. Gratis e instantaneas.
2. Modelo (function calling): solo lo que las reglas no resolvieron.
3. Validacion del servidor: categorias y metodos DEBEN existir en la cuenta del
   usuario; si no, cae a "Otros" y se avisa.

Este modulo NO escribe nada en la base: devuelve propuestas. El guardado vive en
POST /captura/confirmar.
"""
import json
import re
from datetime import date, timedelta

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.finance import Account, Category, PaymentMethod, Transaction
from app.services import colombia as co

# Las categorias que el modelo puede proponer. Se resuelven contra las que el
# usuario tiene de verdad; si no existe, cae a Otros.
CATEGORIAS = [
    "Comida", "Mercado", "Transporte", "Vivienda", "Servicios", "Salud",
    "Ocio", "Educacion", "Familia", "Impuestos", "Otros",
    "Salario", "Freelance",
]
GASTO_ESPERADAS = {"Comida", "Mercado", "Transporte", "Vivienda", "Servicios",
                   "Salud", "Ocio", "Educacion", "Familia", "Impuestos"}

TOOL = {
    "type": "function",
    "function": {
        "name": "registrar_movimientos",
        "description": (
            "Registra uno o varios movimientos financieros extraidos de un texto "
            "informal. Llámala aunque el texto mencione UN solo gasto."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "movimientos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tipo": {"type": "string", "enum": ["gasto", "ingreso"]},
                            "monto": {
                                "type": "number",
                                "description": (
                                    "0 si el texto NO da el monto. Nunca inventes una cifra: "
                                    "si no está, pon 0."
                                ),
                            },
                            # SIN enum a proposito: Groq valida el enum del lado del
                            # servidor y devuelve 400 "Tool call validation" si el
                            # modelo escribe algo fuera de la lista. Medido: escribia
                            # "Educación" con tilde y el enum decia "Educacion".
                            # El backend valida y normaliza despues (_validar), y
                            # cae a "Otros" si no existe. Aqui solo orientamos.
                            "categoria": {
                                "type": "string",
                                "description": (
                                    "Una de: " + ", ".join(CATEGORIAS) + ". "
                                    "Usa la más cercana. Si no encaja ninguna, 'Otros'."
                                ),
                            },
                            "descripcion": {
                                "type": "string",
                                "description": "El texto tal cual lo dijo el usuario, corto.",
                            },
                            "metodo": {
                                "type": ["string", "null"],
                                "description": (
                                    "Efectivo, Nequi, Daviplata, Dale, PSE, Nómina, "
                                    "Tarjeta o Transferencia. null si el texto no menciona uno."
                                ),
                            },
                            "fecha": {
                                # type como lista para admitir null. Decir "usa null" en
                                # la descripción mientras se declara "string" hace que
                                # Groq rechace la llamada con 400 "tool call validation".
                                "type": ["string", "null"],
                                "description": "YYYY-MM-DD, o null si el texto no dice fecha.",
                            },
                            "fijo": {
                                "type": "boolean",
                                "description": "true si es un gasto recurrente fijo "
                                              "(arriendo, servicio, suscripción, cuota).",
                            },
                            # type como lista para admitir null, igual que "fecha".
                            "frecuencia": {
                                "type": ["string", "null"],
                                "description": (
                                    "La periodicidad que el texto declara: 'mensual', "
                                    "'quincenal' o 'semanal'. 'cada quincena' es "
                                    "quincenal, 'cada semana' semanal, 'cada mes' "
                                    "mensual. Solo si el texto la dice; si no, null."
                                ),
                            },
                            "dia_fijo": {
                                "type": ["integer", "null"],
                                "description": (
                                    "Dia del mes (1-31) en que cae el fijo, si el texto "
                                    "lo dice ('el 20 de cada mes'). null si no lo dice."
                                ),
                            },
                            "dia_semana": {
                                "type": ["integer", "null"],
                                "description": (
                                    "Para un fijo semanal, el dia de la semana en que "
                                    "cae: 0=lunes, 1=martes, 2=miercoles, 3=jueves, "
                                    "4=viernes, 5=sabado, 6=domingo. 'me pagan cada "
                                    "domingo' es 6. null si el texto no nombra un dia."
                                ),
                            },
                        },
                        "required": ["tipo", "monto", "categoria", "descripcion"],
                    },
                }
            },
            "required": ["movimientos"],
        },
    },
}

SYSTEM = """Eres el capturador de CTD, una app de finanzas para Colombia.
Conviertes texto informal en movimientos y SIEMPRE llamas la herramienta registrar_movimientos.

Vocabulario colombiano:
- "lucas" y "mil" valen 1000; "millones" vale 1.000.000; "media luna" 50.000.
- corrientazo/almuerzo -> Comida. mercado/supermercado/pesquería -> Mercado.
- taxi/uber/bomba -> Transporte. recibo de luz/agua, internet, gas -> Servicios.
- arriendo/alquiler -> Vivienda. farmacia/doctor -> Salud. fiesta -> Ocio.
- quincena/nómina/salario/prima -> Salario (ingreso).
- Nequi, Daviplata, Dale, PSE, Nómina son métodos de pago, no categorías.

Reglas que no puedes romper:
- Un texto puede traer VARIOS movimientos. Sácalos todos, uno por llamada.
- "me pagan", "me transfirieron", "gané" son INGRESOS; "pagué" es gasto.
- NUNCA inventes un monto. Si el texto no dice cuánto, pon 0.
- NUNCA inventes un movimiento. Si el texto no habla de plata (salvo que ya te
  digamos que hay indicios), llama a la herramienta con la lista VACÍA. Es
  preferible decir "no vi nada" que inventar un gasto de monto cero.
- La categoría debe ser una de la lista.
- El monto va como número plano: 18.000 es 18000, "1,5 millones" es 1500000,
  "un millón y medio" es 1500000.
- Si el texto declara periodicidad ("cada quincena", "cada semana", "cada 15
  días"), pon fijo=true Y la frecuencia que dijo. Si no la declara, null.
- Un día de la semana con "cada" o "todos los" ("cada domingo", "todos los
  viernes") es un fijo SEMANAL: pon esa frecuencia y el día en dia_semana."""


class CapturaError(Exception):
    pass


def _httpx_post(cuerpo: dict) -> dict:
    if not settings.openai_api_key:
        raise CapturaError("Asesor no configurado: falta OPENAI_API_KEY.")
    r = httpx.post(
        f"{settings.asesor_base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        json=cuerpo,
        timeout=45,
    )
    if r.status_code == 429:
        raise CapturaError("El capturador está ocupado. Intenta en un momento.")
    if r.status_code >= 400:
        # El cuerpo importa: un 400 sin detalle deja a ciegas tanto al usuario
        # como al que depura. Se incluyen los primeros 300 caracteres.
        detalle = ""
        try:
            cuerpo_err = r.json().get("error", {})
            detalle = cuerpo_err.get("message") or json.dumps(cuerpo_err)[:300]
        except Exception:
            detalle = r.text[:300]
        raise CapturaError(f"El proveedor rechazó la petición ({r.status_code}): {detalle[:280]}")
    return r.json()


def _pistas(texto: str, db: Session) -> dict:
    """Lo que las reglas deterministas YA saben. Se le pasa al modelo para que no
    tenga que adivinar lo obvio, y para poder contrastar sus respuestas."""
    modismos = co.buscar_modismos(texto, db)
    return {
        "montos_detectados": [m[0] for m in co.montos_en_texto(texto)],
        "metodo_detectado": co.metodo_por_texto(texto),
        "tipo_sugerido": co.tipo_por_texto(texto),
        "fecha_detectada": (co.resolver_fecha(texto).isoformat()
                            if co.resolver_fecha(texto) else None),
        "modismos": sorted({f"{m['termino']}->{m['categoria']}" for m in modismos}),
    }


def _categorias_usuario(db: Session, perfil_id: str) -> dict[str, Category]:
    return {co.normalizar(c.nombre): c
            for c in db.query(Category).filter_by(perfil_id=perfil_id).all()}


def _metodos_usuario(db: Session, user_id: str) -> dict[str, PaymentMethod]:
    return {co.normalizar(m.nombre): m
            for m in db.query(PaymentMethod).filter_by(user_id=user_id).all()}


def _tiene_indicios(texto: str, db: Session) -> bool:
    """¿Esto se parece siquiera a un movimiento financiero?

    Sin esta puerta, el modelo inventa un gasto para CUALQUIER texto: medido,
    "asdkjhaskdjh" devolvio un gasto de monto 0 con categoria real, y "mm" igual.
    Con solo "no inventes montos" no alcanza: el problema es que fabricate el
    movimiento entero, no el monto.

    Exigir evidencia aqui ademas ahorra la llamada: un "@" suelto no consume
    tokens ni cuota del usuario.
    """
    t = co.normalizar(texto)
    if co.montos_en_texto(texto):
        return True
    if co.buscar_modismos(texto, db):
        return True
    if co.tipo_por_texto(texto):
        return True
    # "y" de union: "gasté 18 mil y 5 mil" no tiene verbo en el segundo trozo.
    return bool(re.search(r"\b(compre|pague|gaste|pago|gasto|saque|me transferencia)\b", t))


SIN_CAPTURA = (
    "No encontré ningún movimiento en ese texto. Prueba algo como: "
    "\"gasté 18 mil en el almuerzo y 5 mil en un taxi con Nequi\"."
)


def transcribir(audio: bytes, nombre: str, mime: str = "") -> str:
    """Transcribe una nota de voz con Whisper.

    El audio NO se guarda: se manda a Groq, se recibe el texto y el binario se
    descarta al salir de esta funcion. Eso es lo que se le promete al usuario en la
    politica de datos, asi que no hay que anadir ningun campo de blob al modelo.

    Se manda como data URL porque el endpoint de Groq de audio acepta base64 y asi
    el archivo nunca toca el disco del servidor.
    """
    if not settings.openai_api_key:
        raise CapturaError("Captura por voz no configurada: falta OPENAI_API_KEY.")
    if not audio:
        raise CapturaError("No llegó el audio.")
    if len(audio) > settings.voz_max_bytes:
        raise CapturaError(
            f"El audio es muy grande (máx {settings.voz_max_bytes // 1_000_000} MB). "
            "Grábalo más corto."
        )
    ext = (nombre.rsplit(".", 1)[-1] if "." in nombre else "webm").lower()[:5]
    if not re.fullmatch(r"[a-z0-9]{2,5}", ext):
        ext = "webm"
    mime = f"audio/{'webm' if ext in ('webm', 'ogg', 'opus') else ext}"
    if mime == "audio/mp4":
        mime = "audio/mp4"

    # El audio va como BINARIO, no como data URL. Medido: Groq responde
    # 400 "could not process file" si recibe un data URL en el multipart, y en
    # cambio acepta los bytes directos. Sigue sin tocarse el disco: se manda
    # desde memoria y el binario muere al salir de esta funcion.
    r = httpx.post(
        f"{settings.asesor_base_url.rstrip('/')}/audio/transcriptions",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        data={
            "model": settings.voz_model,
            # El español colombiano no trae por defecto el acento y la IA lo inventa.
            "language": "es",
            "prompt": (
                "Registros de gastos en Colombia: lucas, mil, millones, corrientazo, "
                "Nequi, Daviplata, la quincena, el arriendo, el recibo de la luz, "
                "el sueldo, la prima, servicios, comida, transporte."
            ),
            "temperature": "0",
        },
        files={"file": (f"nota.{ext}", audio, mime)},
        timeout=90,
    )
    if r.status_code == 429:
        raise CapturaError("El capturador está ocupado. Intenta en un momento.")
    if r.status_code >= 400:
        detalle = r.text[:280]
        try:
            detalle = (r.json().get("error") or {}).get("message", detalle)
        except Exception:
            pass
        raise CapturaError(f"No pude transcribir el audio ({r.status_code}): {detalle[:240]}")
    texto = (r.json().get("text") or "").strip()
    if not texto:
        raise CapturaError("No alcancé a entender el audio. Intenta de nuevo más cerca del micrófono.")
    if len(texto) > 500:
        texto = texto[:500]
    return texto


def analizar(texto: str, db: Session, user_id: str, perfil_id: str) -> dict:
    """Devuelve una PROPUESTA. No escribe nada."""
    texto = (texto or "").strip()
    if not texto:
        raise CapturaError("Escribe algo para capturar.")
    if len(texto) > 500:
        texto = texto[:500]
    if not _tiene_indicios(texto, db):
        raise CapturaError(SIN_CAPTURA)

    pistas = _pistas(texto, db)
    cuerpo = {
        "model": settings.asesor_model,
        "temperature": 0.1,
        # Extraccion: NO bajar reasoning_effort, se equivoca en metodo y categoria.
        "max_tokens": settings.asesor_max_tokens,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content":
                f"Texto del usuario: {texto}\n\n"
                f"Lo que YA detectamos con reglas (úsalo, no lo repitas como duda):\n"
                f"{json.dumps(pistas, ensure_ascii=False)}\n\n"
                f"Categorías disponibles del usuario: "
                f"{', '.join(c.nombre for c in db.query(Category).filter_by(perfil_id=perfil_id).all())}"},
        ],
        "tools": [TOOL],
        "tool_choice": "auto",
    }
    data = _httpx_post(cuerpo)
    msg = ((data.get("choices") or [{}])[0].get("message") or {})
    calls = msg.get("tool_calls") or []
    if not calls:
        texto_salida = (msg.get("content") or "").strip()
        raise CapturaError(
            "No entendí esa frase. Prueba algo como: "
            "\"gasté 18 mil en el almuerzo y 5 mil en un taxi con Nequi\"."
            + (f" ({texto_salida[:120]})" if texto_salida else "")
        )

    try:
        args = json.loads(calls[0]["function"]["arguments"] or "{}")
    except json.JSONDecodeError:
        raise CapturaError("No pude interpretar la respuesta. Intenta de nuevo.")
    crudos = args.get("movimientos") or []
    if not crudos:
        raise CapturaError(
            "No encontré ningún movimiento en ese texto. Prueba algo como: "
            "\"gasté 18 mil en el almuerzo y 5 mil en un taxi con Nequi\"."
        )

    return _validar(crudos, texto, pistas, db, user_id, perfil_id)


def _validar(crudos: list, texto: str, pistas: dict, db: Session,
             user_id: str, perfil_id: str) -> dict:
    """Contrasta la propuesta del modelo contra lo que el usuario realmente tiene."""
    cats = _categorias_usuario(db, perfil_id)
    mets = _metodos_usuario(db, user_id)
    cuentas = db.query(Account).filter_by(perfil_id=perfil_id).order_by(Account.nombre).all()
    cuenta_por_defecto = cuentas[0] if cuentas else None
    metodo_por_defecto = next((m for m in mets.values() if "efectivo" in co.normalizar(m.nombre)), None)

    montos_texto = set(round(float(m), 2) for m in pistas["montos_detectados"])
    hoy = date.today()

    propuestos, avisos = [], []
    for i, c in enumerate(crudos):
        tipo = "ingreso" if str(c.get("tipo", "gasto")).lower() == "ingreso" else "gasto"
        try:
            monto = round(float(c.get("monto") or 0), 2)
        except (TypeError, ValueError):
            monto = 0.0

        descripcion = (c.get("descripcion") or "").strip()[:120]

        # El diccionario de modismos es curado y gratis, asi que cuando el modelo
        # lo nombra en la descripcion le gana. Medido: el modelo puso "Transporte"
        # para "corrientazo", que es Comida.
        modismos_conf = [m for m in co.buscar_modismos(descripcion or texto[:60], db)
                         if m["prioridad"] >= 10 and m["categoria"] != "Otros"]
        cat_pedida = str(c.get("categoria") or "Otros")
        if modismos_conf:
            cat_pedida = modismos_conf[0]["categoria"]
            if co.normalizar(cat_pedida) != co.normalizar(str(c.get("categoria") or "")):
                avisos.append(
                    f"Ajusté \"{descripcion}\" a {cat_pedida}: "
                    f"{modismos_conf[0]['termino']} sí es {cat_pedida}."
                )

        cat_nombre = co.normalizar(cat_pedida)
        cat = cats.get(cat_nombre)
        if cat is None:
            # Second pass: buscar por coincidencia parcial ("Comida" vs "comidas").
            for k, v in cats.items():
                if k and (k in cat_nombre or cat_nombre in k):
                    cat = v
                    break
        if cat is None or cat_nombre in ("", "otros"):
            cat = next((v for k, v in cats.items() if k == "otros"), None)
            if cat is None:
                avisos.append("No encontré la categoría 'Otros'; revisa la propuesta.")
        if cat is not None and tipo == "gasto" and cat.tipo == "ingreso":
            avisos.append(f"\"{cat.nombre}\" es de ingresos y se registró como gasto.")

        met = None
        m_nombre = co.normalizar(str(c.get("metodo") or "")) if c.get("metodo") else None
        if m_nombre:
            met = mets.get(m_nombre)
            for k, v in mets.items():
                if met is None and k and k in m_nombre:
                    met = v
        if met is None:
            met = metodo_por_defecto

        # Fecha: la del modelo solo si es valida; si no, la de las reglas; si no, hoy.
        fecha = None
        crudo_fecha = str(c.get("fecha") or "")
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", crudo_fecha)
        if m:
            try:
                cand = hoy.replace(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                fecha = cand if cand <= hoy else None
            except ValueError:
                fecha = None
        if fecha is None and pistas.get("fecha_detectada"):
            fecha = hoy.fromisoformat(pistas["fecha_detectada"])
        if fecha is None:
            fecha = hoy
        # RN-03: nunca mas de un dia al futuro.
        if fecha > hoy:
            fecha = hoy

        # Frecuencia del fijo: primero la del modelo ('cada quincena' del texto);
        # si no la trajo o trajo basura, la regla determinista la busca igual.
        # Si ninguna la vio, queda None y la confirmación crea el fijo mensual
        # con el día del movimiento, como siempre.
        frec_modelo = str(c.get("frecuencia") or "").strip().lower()
        frecuencia = frec_modelo if frec_modelo in ("mensual", "quincenal", "semanal") \
            else co.frecuencia_por_texto(texto)
        dia_fijo = None
        try:
            d = int(c.get("dia_fijo"))
            if 1 <= d <= 31:
                dia_fijo = d
        except (TypeError, ValueError):
            pass
        # "me pagan 63 mil cada domingo": el modelo trae el dia de la semana; si
        # no, la regla determinista lo busca igual. Solo tiene sentido si el
        # fijo es semanal, asi que en los demas casos se descarta.
        dia_semana = None
        try:
            ds = int(c.get("dia_semana"))
            if 0 <= ds <= 6:
                dia_semana = ds
        except (TypeError, ValueError):
            pass
        if dia_semana is None:
            dia_semana = co.dia_semana_por_texto(texto)
        if frecuencia != "semanal":
            dia_semana = None
        # Un semanal sin dia del mes declarado cae en el ultimo dia de ese dia de
        # la semana que ya paso: asi el fijo nace con una fecha real y no con el 1.
        if dia_semana is not None and dia_fijo is None:
            dia_fijo = (hoy - timedelta(days=(hoy.weekday() - dia_semana) % 7)).day

        # El monto aparece tal cual en el texto? Si no, el modelo lo dedujo y hay
        # que pedir confirmacion explicita (decision del usuario).
        monto_explicito = monto > 0 and (round(monto, 2) in montos_texto)
        falta_monto = monto <= 0

        propuestos.append({
            "ix": i,
            "tipo": tipo,
            "monto": monto,
            "falta_monto": falta_monto,
            # True = hay que confirmar el monto antes de guardar, porque el modelo
            # no lo leyó del texto (o no lo había).
            "requiere_confirmacion_monto": falta_monto or not monto_explicito,
            "monto_explicito": monto_explicito,
            "categoria_id": cat.id if cat else None,
            "categoria": cat.nombre if cat else None,
            "descripcion": descripcion,
            "metodo_id": met.id if met else None,
            "metodo": met.nombre if met else None,
            "fecha": fecha.isoformat(),
            "fijo": bool(c.get("fijo")),
            "frecuencia": frecuencia,
            "dia_fijo": dia_fijo,
            "dia_semana": dia_semana,
        })

    pendientes = [p for p in propuestos if p["requiere_confirmacion_monto"]]
    return {
        "texto": texto,
        "movimientos": propuestos,
        "pistas": pistas,
        "avisos": avisos,
        "requiere_confirmacion_monto": bool(pendientes),
        "total": round(sum(p["monto"] for p in propuestos if p["tipo"] == "gasto"), 2),
        "cuenta_por_defecto": cuenta_por_defecto.id if cuenta_por_defecto else None,
        "sin_cuenta": cuenta_por_defecto is None,
        "sin_metodo": metodo_por_defecto is None,
    }