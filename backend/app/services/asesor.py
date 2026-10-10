"""Asesor IA (plan separado): consejos con el contexto RC del usuario, no genéricos.

- El contexto lo arma el SERVIDOR (resumen, presupuestos, metas, fijos, top categorías).
- El modelo NO calcula: para cualquier cifra llama a las herramientas de
  services/asesor_tools.py, que envuelven el motor determinista de
  services/finanzas.py. Medido: con contexto en texto el modelo inventaba
  simbolos y cifras; con herramientas, las respuestas salen ancladas.
- La IA nunca ve credenciales ni otros usuarios. Topes: ASESOR_MAX_TOKENS por
  respuesta (mín. ~2000 si el modelo razona), cuota diaria por plan y timeout 45s.
- Sin OPENAI_API_KEY responde 503 explicativo en vez de romperse.
"""
import httpx
import json
from datetime import date
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.finance import Budget, Category, Transaction
from app.models.goals import Goal, GoalAporte
from app.services.calculos import (
    ahorro_requerido_mensual,
    balance_mes,
    meta_faltante,
    meses_restantes,
    presupuesto_porcentaje,
    tasa_ahorro,
)
from app.services.formato import normalizar_numeros

SYSTEM = """Eres el Asesor de CTD, app de finanzas personales. Hablas español cotidiano,
breve y claro, sin tecnicismos. PROHIBIDO inventar cifras: todo número que menciones
debe venir de una herramienta o del CONTEXTO. Si no tienes el dato, llama a la
herramienta; si no existe la herramienta que lo da, dilo que no lo tienes.
Puedes explicar balances, presupuestos, metas, fijos y hábitos de gasto.
PROHIBIDO: recomendar inversiones, créditos o impuestos específicos; si lo piden,
da educación general y sugiere un profesional. Los aportes a metas son solo
seguimiento: no mueven dinero de sus cuentas. Cierra con una acción concreta
cuando aplique. Máximo 130 palabras.

FORMATO: escribe los montos como los recibes en las herramientas, con PUNTO de
miles y sin símbolo (1780000 -> 1.780.000). No uses espacios finos como
separador ni commas de miles (nunca 1,480,000 ni "1 480 000")."""


def contexto(db: Session, user_id: str, mes: str, moneda: str = "COP") -> str:
    from app.api.v1.recurrentes import _resumen
    from app.services.formato import fecha_es, numero_es, porcentaje

    ing = float(db.query(func.coalesce(func.sum(Transaction.monto), 0)).filter(
        Transaction.user_id == user_id, Transaction.tipo == "ingreso",
        func.to_char(Transaction.fecha, "YYYY-MM") == mes).scalar() or 0)
    gas = float(db.query(func.coalesce(func.sum(Transaction.monto), 0)).filter(
        Transaction.user_id == user_id, Transaction.tipo == "gasto",
        func.to_char(Transaction.fecha, "YYYY-MM") == mes).scalar() or 0)
    bal = balance_mes(ing, gas)
    # La moneda va explicita: sin esto el modelo inventa simbolos (medido: respondio "€"
    # a un usuario COP). Los montos van sin separador de miles para que el modelo no
    # los interprete como varios numeros.
    lineas = [
        f"MONEDA DEL USUARIO: {moneda}. Usa {moneda} en todas las cifras, sin simbolo. "
        f"NO inventes ni conviertas a otra moneda.",
        f"Mes {fecha_es(mes)} ({mes}): ingresos {numero_es(ing)}, "
        f"gastos {numero_es(gas)}, balance {numero_es(bal)} "
        f"(tasa de ahorro {porcentaje(tasa_ahorro(ing, bal))}).",
    ]
    # Ingresos y gastos fijos: el chatbot no puede razonar sobre compromisos sin esto.
    fijos = _resumen(db, user_id, mes)
    if fijos["cantidad"]:
        lineas.append(
            f"Fijos declarados: ingresos {numero_es(fijos['ingresos_fijos_mes'])}, "
            f"gastos {numero_es(fijos['gastos_fijos_mes'])}, "
            f"neto {numero_es(fijos['neto_fijo_mes'])} al mes. "
            f"El {porcentaje(fijos['ratio_fijo'])} de sus gastos del mes son fijos.")
    for b in db.query(Budget).filter_by(user_id=user_id, periodo=mes).all():
        g = float(db.query(func.coalesce(func.sum(Transaction.monto), 0)).filter(
            Transaction.user_id == user_id, Transaction.categoria_id == b.categoria_id,
            Transaction.tipo == "gasto", func.to_char(Transaction.fecha, "YYYY-MM") == mes).scalar() or 0)
        cat = db.get(Category, b.categoria_id)
        lineas.append(f"Presupuesto {cat.nombre if cat else '?'}: gastado {numero_es(g)} "
                      f"de {numero_es(float(b.monto))} "
                      f"({porcentaje(presupuesto_porcentaje(float(b.monto), g))}).")
    for m in db.query(Goal).filter_by(user_id=user_id).all():
        ah = float(db.query(func.coalesce(func.sum(GoalAporte.monto), 0)).filter_by(goal_id=m.id).scalar() or 0)
        fal = meta_faltante(float(m.objetivo), ah)
        mr = meses_restantes(m.fecha_objetivo, date.today())
        req = ahorro_requerido_mensual(fal, mr)
        req_txt = f"{numero_es(req)}/mes" if req is not None else "sin fecha, aporta a tu ritmo"
        lineas.append(f"Meta {m.nombre}: ahorrado {numero_es(ah)} de "
                      f"{numero_es(float(m.objetivo))}, faltan {numero_es(fal)}, "
                      f"requerido {req_txt}.")
    top = db.query(Category.nombre, func.coalesce(func.sum(Transaction.monto), 0)).join(
        Transaction, Transaction.categoria_id == Category.id).filter(
        Transaction.user_id == user_id, Transaction.tipo == "gasto").group_by(
        Category.nombre).order_by(func.sum(Transaction.monto).desc()).limit(3).all()
    if top:
        lineas.append("Top gasto histórico: " + ", ".join(f"{n} {numero_es(t)}" for n, t in top) + ".")
    return "\n".join(lineas)[:4000]


_MODELO_RAZONAMIENTO = ("gpt-oss", "o1", "o3", "o4", "gpt-5")
MAX_RONDAS_HERRAMIENTAS = 3


def _pide_razonamiento(modelo: str) -> bool:
    m = modelo.lower()
    return any(m.startswith(p) or p in m for p in _MODELO_RAZONAMIENTO)


def _post(cuerpo: dict) -> dict:
    r = httpx.post(
        f"{settings.asesor_base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        json=cuerpo,
        timeout=45,
    )
    if r.status_code == 429:
        raise RuntimeError("El asesor está saturado. Intenta en unos minutos.")
    if r.status_code == 404:
        raise RuntimeError("Modelo de IA no existe o sin acceso (revisa ASESOR_MODEL).")
    try:
        r.raise_for_status()
    except Exception:
        raise RuntimeError(f"UPSTREAM_{r.status_code}: El proveedor de IA rechazó la petición (revisa clave y modelo).")
    return r.json()


def _armar(messages: list[dict], max_tokens: int, con_tools: bool) -> dict:
    cuerpo: dict = {"model": settings.asesor_model, "temperature": 0.3,
                    "max_tokens": max_tokens, "messages": messages}
    if con_tools:
        from app.services.asesor_tools import HERRAMIENTAS

        cuerpo["tools"] = HERRAMIENTAS
        cuerpo["tool_choice"] = "auto"
    elif settings.asesor_reasoning_effort and _pide_razonamiento(settings.asesor_model):
        # Solo los modelos de razonamiento aceptan esto; a gpt-4o-mini le da 400.
        cuerpo["reasoning_effort"] = settings.asesor_reasoning_effort
    return cuerpo


def preguntar(mensaje: str, ctx: str, db: Session | None = None,
              user_id: str | None = None, mes: str | None = None,
              historial: list | None = None) -> tuple[str, int]:
    """Responde usando herramientas contra el motor de calculo.

    Sin db/user_id cae al modo sin herramientas (util para pruebas); con ellos, el
    bucle tool-calling es el camino normal.
    """
    if not settings.openai_api_key:
        raise RuntimeError("Asesor no configurado: falta OPENAI_API_KEY.")
    tope = settings.asesor_max_tokens
    usar_tools = db is not None and user_id is not None

    base = [{"role": "system",
             "content": f"{SYSTEM}\n\nCONTEXTO DEL USUARIO:\n{ctx}"}]
    # Historial real como turnos user/assistant. Se recorta para no reventar el contexto.
    for m in (historial or [])[-6:]:
        base.append({"role": "assistant" if m.rol == "assistant" else "user",
                     "content": (m.contenido or "")[:600]})
    base.append({"role": "user", "content": (mensaje or "")[:1000]})
    texto, finish, tokens = "", "", 0

    for ronda in range(1, MAX_RONDAS_HERRAMIENTAS + 1):
        data = _post(_armar(base, tope if ronda == 1 else tope * 2, usar_tools))
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        finish = choice.get("finish_reason") or ""
        tokens += int((data.get("usage") or {}).get("total_tokens", 0))
        texto = (msg.get("content") or "").strip()
        calls = msg.get("tool_calls") or []
        if not calls or not usar_tools:
            break
        # El turno del asistente debe viajar tal cual (con sus tool_calls) antes del tool.
        base.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls", "reasoning")
                     and v is not None})
        for c in calls:
            fn = (c.get("function") or {})
            nombre = fn.get("name") or ""
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            from app.services.asesor_tools import ejecutar

            resultado = ejecutar(nombre, args, db, user_id, mes)
            base.append({"role": "tool", "tool_call_id": c.get("id"),
                         "content": json.dumps(resultado, ensure_ascii=False)})

    # Los modelos de razonamiento pueden gastar todo el presupuesto pensando y devolver
    # content vacio con finish_reason="length". Antes eso llegaba al chat como burbuja en
    # blanco (bug reportado por el usuario); ahora se reintenta con mas margen.
    if not texto and finish == "length":
        data = _post(_armar(base, min(tope * 4, 8000), False))
        choice = (data.get("choices") or [{}])[0]
        texto = ((choice.get("message") or {}).get("content") or "").strip()
        tokens += int((data.get("usage") or {}).get("total_tokens", 0))
    if not texto:
        raise RuntimeError(
            "El asesor no devolvió texto (se agotó el presupuesto de tokens). "
            "Sube ASESOR_MAX_TOKENS o cambia ASESOR_MODEL."
        )
    return normalizar_numeros(texto), tokens
