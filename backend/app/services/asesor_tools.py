"""Herramientas del asesor IA: expone el motor de calculo como funciones OpenAI.

Por que esto existe: medido, gpt-oss-20b con contexto en texto ADIVINA las cifras
(respondio "€" a un usuario COP y calculo metas sin verificarlas). Con function
calling el modelo pide el dato, el backend lo calcula con services/finanzas.py
(determinista) y el modelo solo lo redacta.

El modelo NUNCA ve el codigo de calculo ni las credenciales: solo recibe el
resultado de la herramienta. Cada herramienta devuelve un dict JSON-serializable.
"""
from datetime import date

from sqlalchemy.orm import Session

from app.models.goals import Goal
from app.models.perfil import Perfil
from app.services import finanzas as fin

# Descripciones en espanol y en segunda persona: el modelo las lee para decidir.
HERRAMIENTAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "resumen_financiero",
            "description": (
                "Estado financiero de un mes: ingresos, gastos, balance, tasa de ahorro "
                "y disponible actual. Usala SIEMPRE antes de afirmar cualquier cifra."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mes": {
                        "type": "string",
                        "description": "Mes en formato YYYY-MM. Si se omite, el mes actual.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "puedo_gastar",
            "description": (
                "Responde si el usuario puede permitirse un gasto concreto. Devuelve el "
                "saldo que le quedaria, como cerraria el mes y el veredicto."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "monto": {"type": "number", "description": "Monto del gasto."},
                    "categoria": {
                        "type": "string",
                        "description": "Nombre de la categoria del gasto, si la menciona.",
                    },
                    "mes": {"type": "string", "description": "YYYY-MM. Opcional."},
                },
                "required": ["monto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ruta_meta",
            "description": (
                "Cuantos meses faltan para cumplir una meta con un aporte mensual dado, "
                "y si se alcanza a tiempo con la fecha objetivo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "aporte_mensual": {"type": "number", "description": "Cuanto ahorra por mes."},
                    "meta": {
                        "type": "string",
                        "description": "Nombre de la meta. Si se omite, usa la mas alcanzable.",
                    },
                },
                "required": ["aporte_mensual"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "proyeccion_financiera",
            "description": (
                "Como se espera que cierre el balance los proximos meses, combinando "
                "gastos fijos declarados y el promedio de gastos variables."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "meses": {
                        "type": "integer",
                        "description": "Cuantos meses proyectar (1 a 24). Default 6.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resumen_fijos",
            "description": (
                "Ingresos y gastos fijos declarados del usuario, y que porcentaje de sus "
                "gastos del mes esta comprometido como fijo."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estado_presupuesto",
            "description": (
                "Como va el presupuesto de una categoria: gastado, restante, porcentaje y "
                "estado (ok, alerta, excedido)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "categoria": {"type": "string", "description": "Nombre de la categoria."},
                    "mes": {"type": "string", "description": "YYYY-MM. Opcional."},
                },
                "required": ["categoria"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "riesgo_mezcla",
            "description": (
                "Revisa si salio plata de las CUENTAS DEL NEGOCIO en gastos personales "
                "(Ocio, Familia, Salud, Educacion, Impuestos). Es el error tipico del "
                "independiente. Usala antes de decir que el negocio va bien."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mes": {"type": "string", "description": "YYYY-MM. Opcional."},
                },
            },
        },
    },
]

NOMBRES = {h["function"]["name"] for h in HERRAMIENTAS}


def _redondear(obj):
    """Los float de Postgres llegan con manyas decimales; se limpian para no gastar tokens."""
    if isinstance(obj, dict):
        return {k: _redondear(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redondear(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, 2)
    return obj


def ejecutar(nombre: str, args: dict, db: Session, user_id: str, perfil_id: str,
             mes: str | None = None) -> dict:
    """Ejecuta una herramienta. Nunca lanza: devuelve el error al modelo para que lo explique."""
    mes = mes or fin.mes_actual()
    try:
        if nombre == "resumen_financiero":
            t = fin.total_mes(db, user_id, perfil_id, args.get("mes") or mes)
            d = fin.disponible(db, user_id, perfil_id)
            return _redondear({"mes": t["mes"], "ingresos": t["ingresos"], "gastos": t["gastos"],
                               "balance_mes": t["balance_mes"], "tasa_ahorro": t["tasa_ahorro"],
                               "disponible": d["total"],
                               "por_cuenta": [{"nombre": c["nombre"], "saldo": c["saldo_actual"]}
                                              for c in d["cuentas"]]})

        if nombre == "puedo_gastar":
            return _redondear(fin.puedo_gastar(db, user_id, perfil_id, float(args["monto"]),
                                               args.get("mes") or mes, args.get("categoria")))

        if nombre == "ruta_meta":
            aporte = float(args["aporte_mensual"])
            meta_nombre = (args.get("meta") or "").strip().lower()
            objetivo = None
            if meta_nombre:
                objetivo = next(
                    (g for g in db.query(Goal).filter_by(user_id=user_id, perfil_id=perfil_id).all()
                     if meta_nombre in g.nombre.lower()), None)
                if objetivo is None:
                    disponibles = [g.nombre for g in
                                     db.query(Goal).filter_by(user_id=user_id, perfil_id=perfil_id).all()]
                    return {"error": f"No hay una meta que se llame '{meta_nombre}'.",
                            "metas_disponibles": disponibles}
            if objetivo is not None:
                return _redondear(fin.ruta_meta(db, user_id, objetivo.id, aporte, date.today()))
            metas = [fin.ruta_meta(db, user_id, g.id, aporte, date.today())
                     for g in db.query(Goal).filter_by(user_id=user_id, perfil_id=perfil_id).all()]
            if not metas:
                return {"error": "El usuario todavia no tiene metas de ahorro registradas."}
            return _redondear({"recomendada": fin.meta_mas_alcanzable(db, user_id, perfil_id),
                               "todas_las_metas": metas})

        if nombre == "proyeccion_financiera":
            n = int(args.get("meses") or 6)
            return _redondear(fin.proyeccion(db, user_id, perfil_id, mes, max(1, min(n, 24))))

        if nombre == "resumen_fijos":
            from app.api.v1.recurrentes import _resumen  # reutiliza la misma forma que la UI

            return _redondear(_resumen(db, user_id, perfil_id, mes))

        if nombre == "estado_presupuesto":
            cat = (args.get("categoria") or "").strip()
            if not cat:
                return {"error": "Falta el nombre de la categoria."}
            return _redondear(fin._presupuesto_de(db, user_id, perfil_id, args.get("mes") or mes, cat)
                              or {"error": f"No se encontro la categoria '{cat}'."})

        if nombre == "riesgo_mezcla":
            # Solo tiene sentido si el usuario tiene un Negocio. Sin el, el
            # detector no puede decir nada y devolveria ruido al modelo.
            from app.services import mezcla as mix

            negocio = (db.query(Perfil).filter_by(user_id=user_id, tipo="negocio").first())
            if not negocio:
                return {"hay_riesgo": False,
                        "mensaje": "El usuario no tiene un perfil de Negocio, asi que no "
                                   "hay mezcla que revisar. Sus datos son personales."}
            return _redondear(mix.detectar(db, user_id, negocio.id, args.get("mes") or mes))

        return {"error": f"Herramienta desconocida: {nombre}"}
    except KeyError as e:
        return {"error": f"Falta el dato '{e.args[0]}' en la llamada."}
    except (ValueError, TypeError) as e:
        return {"error": f"Dato invalido: {e}"}
    except Exception as e:  # noqa: BLE001 - el modelo debe saber que fallo, no reventar
        return {"error": f"No se pudo calcular: {type(e).__name__}: {e}"}
