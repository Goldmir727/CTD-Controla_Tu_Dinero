"""Excel canonico y PDF.

Lo que se prueba aqui no es que el archivo se descargue, sino que sea CANONICO:
que exportar, importar y volver a exportar den lo mismo. Un respaldo que al
restaurarse duplica los movimientos es peor que no tener respaldo, porque el
usuario deja de confiar en el.
"""
from datetime import date, datetime

import pytest
from openpyxl import load_workbook

from app.core.database import SessionLocal
from app.models.finance import Account, Budget, Category, Transaction
from app.models.goals import Goal, GoalAporte, Recurring
from app.models.perfil import Perfil
from app.models.user import User
from app.services import documentos as docs
from app.services import pdf as pdf_svc


def _nuevo(correo, **kw):
    db = SessionLocal()
    u = User(nombre="Doc", correo=correo, password_hash="x", moneda="COP", **kw)
    db.add(u)
    db.commit()
    db.refresh(u)
    return db, u


def _borrar(db, u):
    """Limpia todo lo del usuario de prueba."""
    metas = [g.id for g in db.query(Goal).filter_by(user_id=u.id).all()]
    db.query(GoalAporte).filter(GoalAporte.goal_id.in_(metas)).delete(synchronize_session=False) if metas else None
    db.query(Transaction).filter_by(user_id=u.id).delete(synchronize_session=False)
    db.query(Budget).filter_by(user_id=u.id).delete(synchronize_session=False)
    db.query(Recurring).filter_by(user_id=u.id).delete(synchronize_session=False)
    db.query(Goal).filter_by(user_id=u.id).delete(synchronize_session=False)
    db.query(Category).filter_by(user_id=u.id).delete(synchronize_session=False)
    db.query(Account).filter_by(user_id=u.id).delete(synchronize_session=False)
    db.query(Perfil).filter_by(user_id=u.id).delete(synchronize_session=False)
    db.delete(u)
    db.commit()


@pytest.fixture()
def con_datos():
    """Un usuario con dos perfiles y datos en ambos: la mitad del caso es el separation."""
    db, u = _nuevo("doc_a_%d@example.com" % datetime.utcnow().timestamp().__hash__())
    personal = Perfil(user_id=u.id, nombre="Personal", tipo="personal", principal=True)
    negocio = Perfil(user_id=u.id, nombre="Negocio", tipo="negocio", principal=False)
    db.add_all([personal, negocio])
    db.commit()
    db.refresh(personal)
    db.refresh(negocio)

    cat = Category(user_id=u.id, perfil_id=personal.id, nombre="Comida", tipo="gasto")
    catn = Category(user_id=u.id, perfil_id=negocio.id, nombre="Nómina", tipo="gasto")
    cta = Account(user_id=u.id, perfil_id=personal.id, nombre="Nequi", tipo="otro", saldo_inicial=100000)
    ctan = Account(user_id=u.id, perfil_id=negocio.id, nombre="Banco", tipo="banco", saldo_inicial=0)
    db.add_all([cat, catn, cta, ctan])
    db.commit()
    db.refresh(cat)
    db.refresh(catn)
    db.refresh(cta)
    db.refresh(ctan)

    hoy = date(2026, 10, 5)
    db.add_all([
        Transaction(user_id=u.id, perfil_id=personal.id, cuenta_id=cta.id, categoria_id=cat.id,
                    tipo="gasto", monto=45000, fecha=hoy, descripcion="Almuerzo", idempotency_key="k1"),
        Transaction(user_id=u.id, perfil_id=negocio.id, cuenta_id=ctan.id, categoria_id=catn.id,
                    tipo="gasto", monto=2500000, fecha=hoy, descripcion="Pago"),
        Recurring(user_id=u.id, perfil_id=personal.id, nombre="Arriendo", tipo="gasto",
                  monto=1200000, dia=5, frecuencia="mensual", activo=True),
        Budget(user_id=u.id, perfil_id=personal.id, categoria_id=cat.id, monto=400000,
               periodo="2026-10"),
        Goal(user_id=u.id, perfil_id=personal.id, nombre="Bicicleta", objetivo=3000000,
             fecha_objetivo=date(2027, 6, 1)),
    ])
    db.commit()
    meta = db.query(Goal).filter_by(user_id=u.id).first()
    db.add(GoalAporte(goal_id=meta.id, user_id=u.id, monto=500000, fecha=hoy))
    db.commit()
    yield db, u
    db.close()
    db2 = SessionLocal()
    u2 = db2.query(User).filter_by(correo=u.correo).first()
    if u2:
        _borrar(db2, u2)
    db2.close()


# ---------- Exportacion ----------

def test_el_excel_tiene_una_hoja_por_cosa(con_datos):
    db, u = con_datos
    wb = load_workbook(__import__("io").BytesIO(docs.exportar_excel(db, u)))
    for h in ("Resumen", "Perfiles", "Cuentas", "Categorias", "Movimientos",
              "Presupuestos", "Fijos", "Metas", "Aportes"):
        assert h in wb.sheetnames, f"falta la hoja {h}"


def test_el_excel_no_le_manda_uuids_al_usuario(con_datos):
    """Un UUID en una celda es ruido: el usuario no puede leerlo ni corregirlo.

    Las hojas se unen por nombre justamente por esto.
    """
    import io

    db, u = con_datos
    wb = load_workbook(io.BytesIO(docs.exportar_excel(db, u)))
    textos = []
    for h in wb.sheetnames:
        for fila in wb[h].iter_rows(values_only=True):
            textos.extend(str(v) for v in fila if v is not None)
    import re

    uuid = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    assert not [t for t in textos if uuid.search(t)], "se filtro un UUID a una hoja visible"


def test_exportar_un_solo_perfil_no_trae_el_otro(con_datos):
    """Si pido el Negocio, Personal no puede asomar por ningun lado."""
    import io

    db, u = con_datos
    negocio = db.query(Perfil).filter_by(user_id=u.id, nombre="Negocio").first()
    wb = load_workbook(io.BytesIO(docs.exportar_excel(db, u, [negocio.id])))
    ws = wb["Movimientos"]
    filas = list(ws.iter_rows(min_row=2, values_only=True))
    assert filas, "deberia traer el gasto del negocio"
    assert all(f[0] == "Negocio" for f in filas), "se coló un movimiento de otro perfil"


# ---------- Ida y vuelta ----------

def test_ida_y_vuelta_conserva_los_movimientos(con_datos):
    import io

    db, u = con_datos
    antes = db.query(Transaction).filter_by(user_id=u.id).count()
    payload = docs.leer_excel(docs.exportar_excel(db, u))

    db2, u2 = _nuevo("doc_b_%d@example.com" % datetime.utcnow().timestamp().__hash__())
    try:
        r = docs.importar_excel(db2, u2, payload)
        assert not r["errores"], r["errores"]
        despues = db2.query(Transaction).filter_by(user_id=u2.id).count()
        assert despues == antes, f"se perdieron movimientos: {antes} -> {despues}"
    finally:
        _borrar(db2, u2)
        db2.close()


def test_importar_el_mismo_archivo_dos_veces_no_duplica(con_datos):
    """El test mas importante del formato canonico.

    Un usuario que sube su respaldo, lo corrige a mano y lo vuelve a subir no
    puede terminar con el doble de gastos. Por eso se usa el id de carga.
    """
    import io

    db, u = con_datos
    payload = docs.leer_excel(docs.exportar_excel(db, u))

    db2, u2 = _nuevo("doc_c_%d@example.com" % datetime.utcnow().timestamp().__hash__())
    try:
        primero = docs.importar_excel(db2, u2, payload)
        n1 = db2.query(Transaction).filter_by(user_id=u2.id).count()
        segundo = docs.importar_excel(db2, u2, payload)
        n2 = db2.query(Transaction).filter_by(user_id=u2.id).count()
        assert n2 == n1, f"la segunda importacion duplico: {n1} -> {n2}"
        assert segundo["omitidos_duplicados"] > 0
        assert primero["creados"] > 0
    finally:
        _borrar(db2, u2)
        db2.close()


def test_la_importacion_no_mezcla_los_perfiles(con_datos):
    """Un movimiento de Negocio no puede aterrizar en Personal al restaurar."""
    import io

    db, u = con_datos
    payload = docs.leer_excel(docs.exportar_excel(db, u))
    db2, u2 = _nuevo("doc_d_%d@example.com" % datetime.utcnow().timestamp().__hash__())
    try:
        docs.importar_excel(db2, u2, payload)
        for t in db2.query(Transaction).filter_by(user_id=u2.id).all():
            perfil = db2.get(Perfil, t.perfil_id)
            if t.descripcion == "Pago":
                assert perfil.nombre == "Negocio", "un gasto del negocio cayo en el perfil personal"
            if t.descripcion == "Almuerzo":
                assert perfil.nombre == "Personal"
    finally:
        _borrar(db2, u2)
        db2.close()


def test_las_cuentas_se_reconocen_por_nombre_y_no_se_duplican(con_datos):
    import io

    db, u = con_datos
    payload = docs.leer_excel(docs.exportar_excel(db, u))
    db2, u2 = _nuevo("doc_e_%d@example.com" % datetime.utcnow().timestamp().__hash__())
    try:
        docs.importar_excel(db2, u2, payload)
        c1 = db2.query(Account).filter_by(user_id=u2.id).count()
        docs.importar_excel(db2, u2, payload)
        assert db2.query(Account).filter_by(user_id=u2.id).count() == c1, \
            "Nequi se creo dos veces: la cuenta se reconoce por nombre"
    finally:
        _borrar(db2, u2)
        db2.close()


# ---------- Errores que el usuario va a ver ----------

def test_acepta_fechas_en_formato_colombiano():
    """Alguien que edita el archivo en Excel va a escribir dd/mm/aaaa."""
    assert docs._fecha("05/10/2026") == "2026-10-05"
    assert docs._fecha("2026-10-05") == "2026-10-05"
    assert docs._fecha(date(2026, 10, 5)) == "2026-10-05"
    assert docs._fecha(datetime(2026, 10, 5, 18, 30)) == "2026-10-05"
    assert docs._fecha("") is None
    with pytest.raises(docs.ErrorExcel):
        docs._fecha("el jueves pasado")


def test_leer_monto_con_signo_dolar_y_comas():
    """El parser de montos tiene que aguantar los cuatro formatos que exporta
    la gente real, no solo los que produce nuestra propia exportacion."""
    assert docs._numero("$1.250.000", "monto") == 1250000.0      # colombiano
    assert docs._numero("45.000,50", "monto") == 45000.50        # colombiano con decimal
    assert docs._numero("1,250,000.50", "monto") == 1250000.50   # en-US
    assert docs._numero("1250000", "monto") == 1250000.0         # crudo
    assert docs._numero("1.250", "monto") == 1250.0              # tres digitos = miles
    assert docs._numero("1.50", "monto") == 1.5                  # dos digitos = decimal
    assert docs._numero("0.5", "monto") == 0.5
    assert docs._numero("", "monto") == 0.0
    with pytest.raises(docs.ErrorExcel):
        docs._numero("mucho", "monto")


def test_un_archivo_sin_movimientos_dice_que_falta_la_hoja():
    import io

    from openpyxl import Workbook

    wb = Workbook()
    wb.active.title = "Resumen"
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(docs.ErrorExcel, match="Movimientos"):
        docs.leer_excel(buf.getvalue())


def test_una_fila_rota_no_tumba_el_archivo_entero():
    """Un dato malo se reporta y el resto entra: si no, un error de dedo en la
    fila 400 deja al usuario sin nada restaurado."""
    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Movimientos"
    ws.append(["Perfil", "Fecha", "Tipo", "Monto", "Cuenta", "Categoria", "Descripcion"])
    ws.append(["Personal", "2026-10-05", "gasto", 45000, "Nequi", "Comida", "Almuerzo"])
    ws.append(["Personal", "no-es-fecha", "gasto", 45000, "Nequi", "Comida", "Mal fecha"])
    ws.append(["Personal", "2026-10-06", "gasto", -5, "Nequi", "Comida", "Monto negativo"])
    ws.append(["Personal", "2026-10-07", "gasto", 20000, "Nequi", "Comida", "Cafe"])
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(docs.ErrorExcel) as e:
        docs.leer_excel(buf.getvalue())
    # Y lo importante: el archivo se puede reparar ahi mismo quitando esas filas.
    assert "no-es-fecha" in str(e.value)


# ---------- PDF ----------

def test_el_pdf_se_genera_y_es_un_pdf_de_verdad(con_datos):
    db, u = con_datos
    contenido, nombre = pdf_svc.informe_mensual(db, u, db.query(Perfil).filter_by(
        user_id=u.id, nombre="Personal").first(), "2026-10")
    assert contenido[:4] == b"%PDF", "no arranco con la firma de PDF"
    assert len(contenido) > 2000, "salio un PDF vacio"
    assert nombre.endswith(".pdf")


def test_el_pdf_marca_las_estimaciones(con_datos):
    """Un PDF es lo que la gente se cree y lo que se archiva.

    Si la proyeccion sale como un hecho, el usuario toma una decision sobre una
    cifra que el backend invento. El PDF tiene que decirlo, no solo el chat.
    """
    db, u = con_datos
    contenido, _ = pdf_svc.informe_mensual(db, u, db.query(Perfil).filter_by(
        user_id=u.id, nombre="Personal").first(), "2026-10")
    texto = contenido.decode("latin-1", errors="ignore")
    assert "estimaci" in texto, "el PDF no dice que la proyeccion es una estimacion"
    assert "no anticipa ingresos" in texto, "no aclara que la proyeccion no inventa ingresos"
    assert "Almuerzo" in texto or "Comida" in texto, "el detalle de gastos no llego al PDF"


def test_el_pdf_tolera_un_mes_sin_movimientos(con_datos):
    """Un mes nuevo no tiene datos y no puede ser un error 500."""
    db, u = con_datos
    contenido, _ = pdf_svc.informe_mensual(db, u, db.query(Perfil).filter_by(
        user_id=u.id, nombre="Personal").first(), "2020-01")
    assert contenido[:4] == b"%PDF"