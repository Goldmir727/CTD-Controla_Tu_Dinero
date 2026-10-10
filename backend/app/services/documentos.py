"""Excel canonico: la forma en que CTD habla con el usuario fuera de la app.

Por que Excel y no JSON: en Colombia la gente lleva sus gastos en una hoja de
calculo, el contador pide un Excel y nadie abre un .json. Si el archivo tiene
UUIDs, el usuario no puede revisar ni corregir nada; si tiene nombres, puede.

Por eso las hojas se unen por NOMBRE y no por id. Al reimportar, "Nequi" se
reconoce por nombre y no por un identificador que cambia en cada dispositivo.

Importante: el Excel es el formato canonico y el JSON queda como version interna
para el backup automatico. Los dos se soportan, pero el que el usuario ve, abre
y manda a un contador es este.
"""
from __future__ import annotations

from datetime import date, datetime
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.models.finance import Account, Budget, Category, PaymentMethod, Transaction
from app.models.goals import Goal, GoalAporte, Recurring
from app.models.perfil import Perfil

VERSION = 3

# Los colores no son adorno: cuando alguien abre el archivo escanea la columna
# "Tipo" para ubicar los gastos. Pintarla ayuda a leerlo de un vistazo.
VERDE = PatternFill("solid", fgColor="D1F2E6")
ROJO = PatternFill("solid", fgColor="FADBD8")
CABECERA = PatternFill("solid", fgColor="1B2A4A")
CABECERA_TXT = Font(bold=True, color="FFFFFF")
TITULO = Font(bold=True, size=14)


def _hoja(wb: Workbook, titulo: str, cabeceras: list[str], filas: list[list],
          anchos: list[int] | None = None, resaltar: int | None = None) -> None:
    ws = wb.create_sheet(titulo)
    ws.append(cabeceras)
    for c in ws[1]:
        c.fill = CABECERA
        c.font = CABECERA_TXT
        c.alignment = Alignment(vertical="center")
    for f in filas:
        ws.append(f)
    if resaltar is not None and len(cabeceras) > resaltar:
        col = resaltar + 1
        for row in ws.iter_rows(min_row=2, max_col=col, min_col=col):
            for c in row:
                if isinstance(c.value, str):
                    if c.value == "gasto":
                        c.fill = ROJO
                    elif c.value == "ingreso":
                        c.fill = VERDE
    for i, ancho in enumerate(anchos or [], start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho
    ws.freeze_panes = "A2"


def _filas_movimientos(txs: list[Transaction], perfiles: dict, cuentas: dict,
                       cats: dict, metodos: dict) -> list[list]:
    filas = []
    for t in txs:
        filas.append([
            perfiles.get(t.perfil_id, ""), str(t.fecha), t.tipo,
            round(float(t.monto), 2), cuentas.get(t.cuenta_id, ""),
            cats.get(t.categoria_id, ""), metodos.get(t.metodo_id, ""),
            t.descripcion or "", t.idempotency_key or "",
        ])
    return filas


def exportar_excel(db, usuario, perfil_ids: list[str] | None = None) -> bytes:
    """Arma el libro completo. Sin perfil_ids, sale todo el usuario."""
    q_perfil = db.query(Perfil).filter_by(user_id=usuario.id)
    perfiles = q_perfil.all()
    if perfil_ids:
        perfiles = [p for p in perfiles if p.id in perfil_ids]
    ids = {p.id for p in perfiles}
    nombres = {p.id: p.nombre for p in perfiles}

    cuentas = {a.id: a.nombre for a in db.query(Account).filter_by(user_id=usuario.id).all()}
    cats = {c.id: c.nombre for c in db.query(Category).filter_by(user_id=usuario.id).all()}
    metodos = {m.id: m.nombre for m in db.query(PaymentMethod).filter_by(user_id=usuario.id).all()}

    txs = [t for t in db.query(Transaction).filter_by(user_id=usuario.id).all()
           if t.perfil_id in ids]

    wb = Workbook()
    ws = wb.active
    ws.title = "Resumen"
    ws["A1"] = "Controla tu Dinero"
    ws["A1"].font = TITULO
    ws["A2"] = f"Cuenta: {usuario.correo}"
    ws["A3"] = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws["A4"] = f"Version del formato: {VERSION}"
    ws["A5"] = "Este archivo es su respaldo. Guardelo: es lo que le sirve si cambia de telefono."

    r = 7
    ws.cell(row=r, column=1, value="Perfil").font = CABECERA_TXT
    ws.cell(row=r, column=1).fill = CABECERA
    ws.cell(row=r, column=2, value="Movimientos").fill = CABECERA
    ws.cell(row=r, column=2).font = CABECERA_TXT
    for p in perfiles:
        r += 1
        propias = [t for t in txs if t.perfil_id == p.id]
        ing = sum(float(t.monto) for t in propias if t.tipo == "ingreso")
        gas = sum(float(t.monto) for t in propias if t.tipo == "gasto")
        ws.cell(row=r, column=1, value=p.nombre)
        ws.cell(row=r, column=2, value=len(propias))
        ws.cell(row=r, column=3, value=round(ing, 2)).number_format = "#,##0.00"
        ws.cell(row=r, column=4, value=round(gas, 2)).number_format = "#,##0.00"
        ws.cell(row=r, column=5, value=round(ing - gas, 2)).number_format = "#,##0.00"
    for col, ancho in zip("ABCDE", (22, 14, 16, 16, 16)):
        ws.column_dimensions[col].width = ancho

    _hoja(wb, "Perfiles",
          ["Nombre", "Tipo", "Principal", "Avisar mezclas"],
          [[p.nombre, p.tipo, bool(p.principal), bool(p.notificar_mezcla)] for p in perfiles],
          [24, 14, 12, 16])

    _hoja(wb, "Cuentas",
          ["Perfil", "Nombre", "Tipo", "Saldo inicial"],
          [[nombres.get(a.perfil_id, ""), a.nombre, a.tipo, float(a.saldo_inicial)]
           for a in db.query(Account).filter_by(user_id=usuario.id).all() if a.perfil_id in ids],
          [20, 28, 14, 16])

    _hoja(wb, "Categorias",
          ["Perfil", "Nombre", "Tipo", "Activa"],
          [[nombres.get(c.perfil_id, ""), c.nombre, c.tipo, bool(c.activa)]
           for c in db.query(Category).filter_by(user_id=usuario.id).all() if c.perfil_id in ids],
          [20, 26, 12, 10])

    _hoja(wb, "Metodos",
          ["Nombre"],
          [[m.nombre] for m in db.query(PaymentMethod).filter_by(user_id=usuario.id).all()],
          [24])

    _hoja(wb, "Movimientos",
          ["Perfil", "Fecha", "Tipo", "Monto", "Cuenta", "Categoria", "Metodo",
           "Descripcion", "Id de carga"],
          _filas_movimientos(txs, nombres, cuentas, cats, metodos),
          [18, 12, 10, 14, 22, 22, 16, 34, 36], resaltar=2)

    _hoja(wb, "Presupuestos",
          ["Perfil", "Categoria", "Periodo", "Monto"],
          [[nombres.get(b.perfil_id, ""), cats.get(b.categoria_id, ""), b.periodo,
            float(b.monto)]
           for b in db.query(Budget).filter_by(user_id=usuario.id).all() if b.perfil_id in ids],
          [20, 24, 12, 16])

    _hoja(wb, "Fijos",
          ["Perfil", "Nombre", "Tipo", "Monto", "Dia", "Frecuencia", "Activo", "Nota"],
          [[nombres.get(r.perfil_id, ""), r.nombre, r.tipo, float(r.monto), r.dia,
            r.frecuencia, bool(r.activo), r.nota or ""]
           for r in db.query(Recurring).filter_by(user_id=usuario.id).all() if r.perfil_id in ids],
          [18, 24, 10, 14, 8, 14, 10, 30], resaltar=2)

    _hoja(wb, "Metas",
          ["Perfil", "Meta", "Objetivo", "Fecha objetivo", "Imagen", "Aportes",
           "Aporte total", "Falta"],
          [[nombres.get(g.perfil_id, ""), g.nombre, float(g.objetivo),
            str(g.fecha_objetivo) if g.fecha_objetivo else "", g.imagen_url or "",
            len(db.query(GoalAporte).filter_by(goal_id=g.id).all()),
            round(sum(float(a.monto) for a in db.query(GoalAporte).filter_by(goal_id=g.id).all()), 2),
            round(max(float(g.objetivo) - sum(float(a.monto) for a in db.query(GoalAporte).filter_by(goal_id=g.id).all()), 2))]
           for g in db.query(Goal).filter_by(user_id=usuario.id).all() if g.perfil_id in ids],
          [18, 26, 16, 16, 30, 10, 14, 16])

    _hoja(wb, "Aportes",
          ["Perfil", "Meta", "Fecha", "Monto"],
          [[nombres.get(g.perfil_id, ""), g.nombre, str(a.fecha), float(a.monto)]
           for g in db.query(Goal).filter_by(user_id=usuario.id).all() if g.perfil_id in ids
           for a in db.query(GoalAporte).filter_by(goal_id=g.id).all()],
          [18, 26, 14, 16])

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------- Importacion ----------

class ErrorExcel(Exception):
    """El archivo no sirve. El mensaje va directo al usuario, sin jerga."""


def _fecha(valor) -> str | None:
    """Acepta fecha real de Excel o texto. Uno de los dos siempre llega."""
    if valor in (None, ""):
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    txt = str(valor).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(txt, fmt).date().isoformat()
        except ValueError:
            continue
    raise ErrorExcel(f'No se entiende la fecha "{txt}". Use aaaa-mm-dd o dd/mm/aaaa.')


def _numero(valor, campo: str, por_defecto: float = 0.0) -> float:
    """Lee un numero como lo escribe una persona.

    Es el punto donde se rompe la mitad de las importaciones. En Colombia el
    separador de miles es el punto y el decimal la coma, y los exportadores no
    son consistentes: mandan "$1.250.000", "1.250.000,50", "1,250,000.50" o
    "1250000". Adivinar mal un monto importa: si "1.500" se lee como 1,5 en vez
    de 1500, el respaldo deja de servir para lo unico para lo que sirve.
    """
    if valor in (None, ""):
        return por_defecto
    txt = str(valor).strip().replace("$", "").replace(" ", "").replace("%", "")
    if txt in ("", "-"):
        return por_defecto

    # Normalizar ANTES de=float(): Python si lee "1.250" como 1,25, y en una
    # hoja colombiana son 1250. Si se hiciera float() primero, ese error pasaria
    # inadvertido y el respaldo quedaria con las cifras multiplicadas por mil.
    tiene_punto, tiene_coma = "." in txt, "," in txt
    if tiene_punto and tiene_coma:
        # El ultimo separador que aparece es el decimal; el otro marca miles.
        if txt.rfind(",") > txt.rfind("."):
            txt = txt.replace(".", "").replace(",", ".")
        else:
            txt = txt.replace(",", "")
    elif tiene_coma:
        # Solo comas: "1,250,000" son miles, "1,50" es decimal.
        txt = txt.replace(",", "") if len(txt.split(",")[-1]) == 3 else txt.replace(",", ".")
    elif tiene_punto:
        # Solo puntos: "1.250.000" son miles, "1.50" es decimal.
        # Tres digitos exactos tras el punto es la convencion colombiana de miles.
        txt = "".join(txt.split(".")) if len(txt.split(".")[-1]) == 3 else txt

    try:
        return float(txt)
    except ValueError:
        raise ErrorExcel(f'El valor "{valor}" de {campo} no es un numero.')


def _bool(valor) -> bool:
    return str(valor).strip().lower() in ("1", "true", "verdadero", "si", "sí", "x", "activo")


def _filas(ws) -> list[dict]:
    """Convierte una hoja en lista de diccionarios usando la primera fila."""
    headers = [str(c.value).strip().lower() if c.value else "" for c in ws[1]]
    out = []
    for fila in ws.iter_rows(min_row=2, values_only=True):
        if not any(v not in (None, "") for v in fila):
            continue
        out.append({headers[i]: v for i, v in enumerate(fila) if i < len(headers)})
    return out


def leer_excel(contenido: bytes) -> dict:
    """Vuelve el payload con la misma forma que /respaldo/import.

    Acepta las dos versiones: nombres en las columnas ("Categoria") o ids
    crudos ("categoria_id"), porque un archivo hecho a mano puede traer cualquiera.
    """
    try:
        wb = load_workbook(BytesIO(contenido), data_only=True)
    except Exception:
        raise ErrorExcel("Ese archivo no se pudo abrir. Debe ser un .xlsx de CTD.")

    if "Movimientos" not in wb.sheetnames:
        raise ErrorExcel('Falta la hoja "Movimientos". Sin esa hoja no hay nada que restaurar.')

    nombres_perfil = _filas(wb["Perfiles"]) if "Perfiles" in wb.sheetnames else []
    cuentas_def = _filas(wb["Cuentas"]) if "Cuentas" in wb.sheetnames else []
    categorias_def = _filas(wb["Categorias"]) if "Categorias" in wb.sheetnames else []
    metodos_def = _filas(wb["Metodos"]) if "Metodos" in wb.sheetnames else []
    presup_def = _filas(wb["Presupuestos"]) if "Presupuestos" in wb.sheetnames else []
    fijos_def = _filas(wb["Fijos"]) if "Fijos" in wb.sheetnames else []
    metas_def = _filas(wb["Metas"]) if "Metas" in wb.sheetnames else []
    aportes_def = _filas(wb["Aportes"]) if "Aportes" in wb.sheetnames else []

    payload = {"version": 2, "perfiles": [], "cuentas": [], "categorias": [], "metodos": [],
               "movimientos": [], "presupuestos": [], "recurrentes": [], "metas": []}
    errores: list[str] = []

    for p in nombres_perfil:
        if p.get("nombre"):
            payload["perfiles"].append({
                "nombre": str(p["nombre"]).strip(),
                "tipo": str(p.get("tipo") or "personal").strip().lower(),
                "principal": _bool(p.get("principal"))})

    for c in cuentas_def:
        if c.get("nombre"):
            payload["cuentas"].append({
                "perfil": c.get("perfil"), "nombre": str(c["nombre"]).strip(),
                "tipo": str(c.get("tipo") or "otro").strip().lower(),
                "saldo_inicial": _numero(c.get("saldo inicial"), "saldo inicial")})

    for c in categorias_def:
        if c.get("nombre"):
            payload["categorias"].append({
                "perfil": c.get("perfil"), "nombre": str(c["nombre"]).strip(),
                "tipo": str(c.get("tipo") or "gasto").strip().lower(),
                "activa": True if c.get("activa") in (None, "") else _bool(c.get("activa"))})

    for m in metodos_def:
        if m.get("nombre"):
            payload["metodos"].append({"nombre": str(m["nombre"]).strip()})

    # Movimientos: la hoja que importa. Cada fila se valida sola, para que un
    # dato malo no tumbe el archivo entero.
    for n, m in enumerate(_filas(wb["Movimientos"]), start=2):
        try:
            fecha = _fecha(m.get("fecha"))
            if not fecha:
                raise ErrorExcel("la fecha esta vacia")
            tipo = str(m.get("tipo") or "gasto").strip().lower()
            if tipo not in ("gasto", "ingreso"):
                raise ErrorExcel(f'el tipo "{tipo}" no es gasto ni ingreso')
            monto = _numero(m.get("monto"), "monto")
            if monto <= 0:
                raise ErrorExcel("el monto debe ser mayor que cero")
            payload["movimientos"].append({
                "perfil": m.get("perfil"), "tipo": tipo, "monto": abs(monto),
                "fecha": fecha, "descripcion": str(m.get("descripcion") or "").strip() or None,
                "cuenta_nombre": str(m.get("cuenta") or "").strip() or None,
                "categoria_nombre": str(m.get("categoria") or "").strip() or None,
                "metodo_nombre": str(m.get("metodo") or "").strip() or None,
                "idempotency_key": str(m.get("id de carga") or "").strip() or None,
                "fila": n})
        except ErrorExcel as e:
            errores.append(f"Movimientos fila {n}: {e}")

    for p in presup_def:
        try:
            payload["presupuestos"].append({
                "perfil": p.get("perfil"), "categoria_nombre": str(p.get("categoria") or "").strip() or None,
                "categoria_id": p.get("categoria_id"),
                "monto": _numero(p.get("monto"), "presupuesto"), "periodo": str(p.get("periodo") or "").strip()})
        except ErrorExcel as e:
            errores.append(f"Presupuestos: {e}")

    for f in fijos_def:
        try:
            payload["recurrentes"].append({
                "perfil": f.get("perfil"), "nombre": str(f.get("nombre") or "Fijo").strip(),
                "tipo": str(f.get("tipo") or "gasto").strip().lower(),
                "monto": _numero(f.get("monto"), "monto del fijo"),
                "dia": int(_numero(f.get("dia"), "dia del fijo", 1)),
                "frecuencia": str(f.get("frecuencia") or "mensual").strip().lower(),
                "activo": True if f.get("activo") in (None, "") else _bool(f.get("activo")),
                "nota": str(f.get("nota") or "").strip() or None})
        except (ErrorExcel, ValueError) as e:
            errores.append(f"Fijos: {e}")

    aportes_por_meta: dict[str, list] = {}
    for a in aportes_def:
        try:
            meta = str(a.get("meta") or "").strip()
            aportes_por_meta.setdefault(meta, []).append(
                {"fecha": _fecha(a.get("fecha")), "monto": _numero(a.get("monto"), "aporte")})
        except ErrorExcel as e:
            errores.append(f"Aportes: {e}")

    for g in metas_def:
        try:
            nombre = str(g.get("meta") or "").strip()
            if not nombre:
                continue
            payload["metas"].append({
                "perfil": g.get("perfil"), "nombre": nombre,
                "objetivo": _numero(g.get("objetivo"), "objetivo"),
                "fecha_objetivo": _fecha(g.get("fecha objetivo")),
                "imagen_url": str(g.get("imagen") or "").strip() or None,
                "aportes": aportes_por_meta.get(nombre, [])})
        except ErrorExcel as e:
            errores.append(f"Metas: {e}")

    if errores:
        raise ErrorExcel("; ".join(errores[:6]) + (f" (+{len(errores) - 6} mas)" if len(errores) > 6 else ""))
    return payload


# ---------- Restauracion ----------

def _perfil_por_nombre(db, usuario, nombre, cache: dict, tipo="personal") -> Perfil:
    """Resuelve (o crea) el perfil de una fila. Todo cuelga de aqui.

    Que la cuenta, la categoria y el movimiento resolved al MISMO perfil es lo
    que impide que restaurar un respaldo mezcle el Personal con el Negocio.
    """
    nombre = (nombre or "Personal").strip() or "Personal"
    if nombre in cache:
        return cache[nombre]
    p = db.query(Perfil).filter_by(user_id=usuario.id, nombre=nombre).first()
    if not p:
        p = Perfil(user_id=usuario.id, nombre=nombre, tipo=tipo, principal=False,
                   notificar_mezcla=True)
        db.add(p)
        db.flush()
    cache[nombre] = p
    return p


def _cuenta_por_nombre(db, usuario, perfil, nombre, tipo="otro") -> Account:
    """Cuentas por nombre y perfil.

    Una hoja de calculo escrita a mano puede traer una cuenta que no existe; se
    crea en vez de fallar, porque el usuario quiere que SUS datos entren, no que
    la app le discuta los nombres.
    """
    nombre = (nombre or "").strip()
    if nombre:
        c = db.query(Account).filter_by(user_id=usuario.id, perfil_id=perfil.id,
                                       nombre=nombre).first()
        if c:
            return c
    else:
        c = db.query(Account).filter_by(user_id=usuario.id, perfil_id=perfil.id).first()
        if c:
            return c
    c = Account(user_id=usuario.id, perfil_id=perfil.id, nombre=nombre or "Efectivo",
                tipo=tipo or "otro", saldo_inicial=0)
    db.add(c)
    db.flush()
    return c


def _categoria_por_nombre(db, usuario, perfil, nombre, tipo="gasto") -> Category | None:
    nombre = (nombre or "").strip()
    if not nombre:
        return None
    c = db.query(Category).filter_by(user_id=usuario.id, perfil_id=perfil.id,
                                    nombre=nombre).first()
    if c:
        return c
    c = Category(user_id=usuario.id, perfil_id=perfil.id, nombre=nombre,
                 tipo=tipo, icono="tag", activa=True)
    db.add(c)
    db.flush()
    return c


def _metodo_por_nombre(db, usuario, nombre) -> PaymentMethod | None:
    nombre = (nombre or "").strip()
    if not nombre:
        return None
    m = db.query(PaymentMethod).filter_by(user_id=usuario.id, nombre=nombre).first()
    if m:
        return m
    m = PaymentMethod(user_id=usuario.id, nombre=nombre)
    db.add(m)
    db.flush()
    return m


def _ya_existe(db, usuario, perfil, t: dict, cuenta: Account) -> bool:
    """Esta fila ya esta? Sin esto, restaurar dos veces duplica los movimientos.

    Se usa el id de carga cuando viene (el export lo escribe). Si el usuario
    borro esa columna, se cae a comparar fecha, monto, tipo y cuenta, que para
    una hoja de gastos real es suficiente y evita el doble cobro en la cara.
    """
    if t.get("idempotency_key"):
        if db.query(Transaction).filter_by(user_id=usuario.id,
                                           idempotency_key=t["idempotency_key"]).first():
            return True
    return bool(db.query(Transaction).filter_by(
        user_id=usuario.id, perfil_id=perfil.id, tipo=t["tipo"],
        monto=abs(float(t["monto"])), fecha=t["fecha"], cuenta_id=cuenta.id,
    ).first())


def importar_excel(db, usuario, payload: dict) -> dict:
    """Restaura el Excel. Idempotente: restoring dos veces no duplica nada."""
    creados, omitidos, errores = 0, 0, []
    perfiles_cache: dict[str, Perfil] = {}

    for pd in payload.get("perfiles", []):
        _perfil_por_nombre(db, usuario, pd.get("nombre"), perfiles_cache, pd.get("tipo", "personal"))
    for p in db.query(Perfil).filter_by(user_id=usuario.id).all():
        perfiles_cache.setdefault(p.nombre, p)

    for m in payload.get("metodos", []):
        if _metodo_por_nombre(db, usuario, m["nombre"]):
            omitidos += 1

    for a in payload.get("cuentas", []):
        perfil = _perfil_por_nombre(db, usuario, a.get("perfil"), perfiles_cache)
        if db.query(Account).filter_by(user_id=usuario.id, perfil_id=perfil.id,
                                       nombre=a["nombre"]).first():
            omitidos += 1
            continue
        db.add(Account(user_id=usuario.id, perfil_id=perfil.id, nombre=a["nombre"],
                       tipo=a.get("tipo", "otro"),
                       saldo_inicial=a.get("saldo_inicial", 0)))
        db.flush()
        creados += 1

    for c in payload.get("categorias", []):
        perfil = _perfil_por_nombre(db, usuario, c.get("perfil"), perfiles_cache)
        nombre = (c["nombre"] or "").strip()
        if not nombre:
            omitidos += 1
            continue
        if db.query(Category).filter_by(user_id=usuario.id, perfil_id=perfil.id,
                                       nombre=nombre).first():
            omitidos += 1
            continue
        db.add(Category(user_id=usuario.id, perfil_id=perfil.id, nombre=nombre,
                        tipo=c.get("tipo", "gasto"),
                        icono=c.get("icono", "tag"),
                        activa=c.get("activa", True)))
        db.flush()
        creados += 1

    for t in payload.get("movimientos", []):
        try:
            perfil = _perfil_por_nombre(db, usuario, t.get("perfil"), perfiles_cache)
            cuenta = _cuenta_por_nombre(db, usuario, perfil, t.get("cuenta_nombre"))
            if _ya_existe(db, usuario, perfil, t, cuenta):
                omitidos += 1
                continue
            cat = _categoria_por_nombre(db, usuario, perfil, t.get("categoria_nombre"), "gasto")
            met = _metodo_por_nombre(db, usuario, t.get("metodo_nombre"))
            db.add(Transaction(user_id=usuario.id, perfil_id=perfil.id, tipo=t["tipo"],
                               monto=abs(float(t["monto"])), fecha=date.fromisoformat(t["fecha"]),
                               descripcion=t.get("descripcion") or "", cuenta_id=cuenta.id,
                               categoria_id=cat.id if cat else None,
                               metodo_id=met.id if met else None,
                               idempotency_key=t.get("idempotency_key")))
            creados += 1
        except (ValueError, TypeError, KeyError) as e:
            errores.append(f"movimiento {t.get('fila', '?')}: {e}")

    for b in payload.get("presupuestos", []):
        try:
            perfil = _perfil_por_nombre(db, usuario, b.get("perfil"), perfiles_cache)
            cat = _categoria_por_nombre(db, usuario, perfil, b.get("categoria_nombre"), "gasto")
            if not cat:
                omitidos += 1
                continue
            if db.query(Budget).filter_by(user_id=usuario.id, perfil_id=perfil.id,
                                          categoria_id=cat.id, periodo=b["periodo"]).first():
                omitidos += 1
                continue
            db.add(Budget(user_id=usuario.id, perfil_id=perfil.id, categoria_id=cat.id,
                          monto=b["monto"], periodo=b["periodo"]))
            creados += 1
        except (ValueError, TypeError, KeyError) as e:
            errores.append(f"presupuesto: {e}")

    for r in payload.get("recurrentes", []):
        try:
            perfil = _perfil_por_nombre(db, usuario, r.get("perfil"), perfiles_cache)
            existe = db.query(Recurring).filter_by(user_id=usuario.id, perfil_id=perfil.id,
                                                   nombre=r["nombre"], dia=r.get("dia", 1)).first()
            if existe:
                omitidos += 1
                continue
            db.add(Recurring(user_id=usuario.id, perfil_id=perfil.id, nombre=r["nombre"],
                             tipo=r.get("tipo", "gasto"), monto=r["monto"],
                             dia=max(1, min(31, int(r.get("dia") or 1))),
                             frecuencia=r.get("frecuencia", "mensual"),
                             activo=r.get("activo", True), nota=r.get("nota")))
            creados += 1
        except (ValueError, TypeError, KeyError) as e:
            errores.append(f"fijo: {e}")

    for g in payload.get("metas", []):
        try:
            perfil = _perfil_por_nombre(db, usuario, g.get("perfil"), perfiles_cache)
            meta = db.query(Goal).filter_by(user_id=usuario.id, perfil_id=perfil.id,
                                            nombre=g["nombre"]).first()
            if not meta:
                meta = Goal(user_id=usuario.id, perfil_id=perfil.id, nombre=g["nombre"],
                            objetivo=g["objetivo"],
                            fecha_objetivo=date.fromisoformat(g["fecha_objetivo"])
                            if g.get("fecha_objetivo") else None,
                            imagen_url=g.get("imagen_url"))
                db.add(meta)
                db.flush()
                creados += 1
            else:
                omitidos += 1
            for a in g.get("aportes", []):
                if db.query(GoalAporte).filter_by(user_id=usuario.id, goal_id=meta.id,
                                                  monto=a["monto"],
                                                  fecha=date.fromisoformat(a["fecha"])).first():
                    omitidos += 1
                    continue
                if float(a["monto"]) <= 0:
                    raise ValueError("aporte debe ser mayor que cero")
                db.add(GoalAporte(goal_id=meta.id, user_id=usuario.id,
                                  monto=a["monto"], fecha=date.fromisoformat(a["fecha"])))
        except (ValueError, TypeError, KeyError) as e:
            errores.append(f"meta {g.get('nombre')}: {e}")

    db.commit()
    return {"creados": creados, "omitidos_duplicados": omitidos, "errores": errores}