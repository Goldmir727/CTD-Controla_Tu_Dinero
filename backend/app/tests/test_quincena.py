"""Tests de la revision quincenal.

Lo que se prueba aqui son los calculos, no el formato: una quincena mal partida
o un ritmo mal calculado hacen que la app diga una falsehood con toda confianza.
"""
from datetime import date

import pytest

from app.services import colombia as co
from app.services import quincena as qn
from app.services import recurrencia as recu

# Octubre de 2026: el 1 cae jueves y los domingos son 4, 11, 18 y 25.
OCT_INI, OCT_MED, OCT_FIN = date(2026, 10, 1), date(2026, 10, 15), date(2026, 10, 31)
Q1, Q2 = (OCT_INI, OCT_MED), (date(2026, 10, 16), OCT_FIN)


def test_ocurrencias_de_un_fijo_en_la_quincena():
    """Un arriendo el dia 5 es de la primera quincena; el del 20, de la segunda.

    Este es el bug que mas dano hace cuando esta mal: el fijo del dia 20
    desaparece del todo y el usuario se entera el dia que ya no le alcanza.
    """
    assert recu.ocurrencias(*Q1, "mensual", 5) == [date(2026, 10, 5)]
    assert recu.ocurrencias(*Q1, "mensual", 20) == []
    assert recu.ocurrencias(*Q2, "mensual", 20) == [date(2026, 10, 20)]
    assert recu.ocurrencias(*Q2, "mensual", 5) == []
    assert recu.ocurrencias(*Q1, "mensual", 15) == [date(2026, 10, 15)]


def test_un_quincenal_cae_una_vez_por_quincena():
    """Cada 15 dias cae una vez en cada quincena, no 'dos veces en la primera'."""
    assert len(recu.ocurrencias(*Q1, "quincenal", 1)) == 1
    assert len(recu.ocurrencias(*Q2, "quincenal", 1)) == 1
    assert len(recu.ocurrencias(*Q1, "quincenal", 10)) == 1
    assert len(recu.ocurrencias(*Q2, "quincenal", 10)) == 1
    # El 20 tambien cae dos veces: antes el "35" no existia y la segunda
    # quincena se perdia entera.
    assert recu.ocurrencias(*Q2, "quincenal", 20) == [date(2026, 10, 20)]
    assert len(recu.ocurrencias(OCT_INI, OCT_FIN, "quincenal", 20)) == 2


def test_un_semanal_caftera_las_dos_quincenas():
    """Desde el dia 1, cada 7 dias: 1, 8, 15 en la primera y 22, 29 en la segunda."""
    assert len(recu.ocurrencias(*Q1, "semanal", 1)) == 3
    assert len(recu.ocurrencias(*Q2, "semanal", 1)) == 2
    # Y en el mes entero son 4 o 5, no dos: un semanal anclado al 18 perdia las
    # semanas del 4 y el 11.
    assert len(recu.ocurrencias(OCT_INI, OCT_FIN, "semanal", 18)) >= 4


def test_frecuencia_desconocida_no_inventa_plata():
    assert recu.ocurrencias(*Q1, "trimestral", 5) == []


def test_la_paga_de_cada_domingo_cae_en_domingos():
    """El caso que rompia: "me pagan 63 mil cada domingo".

    Con el dia del mes como ancla, el fijo caia el 18 y el 25 de octubre y el 18
    de noviembre (un miercoles). Un domingo no es un dia del mes.
    """
    octubre = recu.ocurrencias(OCT_INI, OCT_FIN, "semanal", 18, 6)
    assert octubre == [date(2026, 10, d) for d in (4, 11, 18, 25)]
    noviembre = recu.ocurrencias(date(2026, 11, 1), date(2026, 11, 30), "semanal", 18, 6)
    assert all(d.weekday() == 6 for d in noviembre)
    assert noviembre[0] == date(2026, 11, 1), "el mes siguiente tiene que seguir en domingo"


def test_la_etiqueta_dice_el_dia_de_la_semana():
    assert recu.etiqueta("semanal", 18, 6) == "cada domingo"
    assert recu.etiqueta("quincenal", 20) == "el 20 y el 5 de cada mes"
    assert recu.etiqueta("mensual", 5) == "el día 5 de cada mes"


def test_febrero_no_revienta_al_pedir_el_dia_30():
    """Bug real: la segunda quincena de febrero pedia el dia 30 y tiraba ValueError.

    Con eso la app daba 500 del 16 al 28 de febrero, todos los años.
    """
    r = co.quincena(date(2026, 2, 20))
    assert r["numero"] == 2
    assert r["fin"] == "2026-02-28"
    assert r["dias_totales"] == 13, "16 a 28 inclusive son 13 dias"


def test_dias_del_mes_respeta_febrero_y_bisiesto():
    assert co.dias_del_mes("2026-02") == 28, "febrero no tiene 30 dias"
    assert co.dias_del_mes("2028-02") == 29, "2028 es bisiesto"
    assert co.dias_del_mes("2026-01") == 31
    assert co.dias_del_mes("2026-04") == 30
    assert co.dias_del_mes("basura") == 30


def test_un_fijo_del_dia_30_cae_en_la_segunda_quincena_de_febrero():
    """Con el bug anterior, el dia 30 en febrero no existia y el fijo se perdia."""
    assert recu.ocurrencias(date(2026, 2, 16), date(2026, 2, 28), "mensual", 30) \
        == [date(2026, 2, 28)]
    assert recu.ocurrencias(date(2026, 2, 16), date(2026, 2, 28), "mensual", 28) \
        == [date(2026, 2, 28)]


def test_la_segunda_quincena_se_compara_con_la_segunda_del_mes_anterior():
    """Comparar la 2a quincena contra la 1a daria un numero sin sentido.

    El gasto tipico de la segunda quincena siempre es menor (se acaba el mes), y el
    usuario leeria "gastaste menos" cuando en realidad esta comparando mitades
    distintas del calendario.
    """
    q = co.quincena(date(2026, 10, 20))
    assert q["numero"] == 2
    anterior = qn._quincena_anterior(q)
    assert anterior is not None
    assert anterior["numero"] == 2, "debe compararse contra la segunda del mes anterior"
    assert anterior["etiqueta"].startswith("2026-09")


def test_la_primera_quincena_se_compara_con_la_primera_del_mes_anterior():
    q = co.quincena(date(2026, 10, 3))
    assert q["numero"] == 1
    anterior = qn._quincena_anterior(q)
    assert anterior["numero"] == 1
    assert anterior["etiqueta"].startswith("2026-09")


def test_el_mes_anterior_no_rompe_en_febrero():
    """Cruzar de enero a febrero es donde un replace(day=1)-timedelta se cae."""
    q = co.quincena(date(2026, 3, 5))
    anterior = qn._quincena_anterior(q)
    assert anterior["etiqueta"].startswith("2026-02")


def test_el_mensaje_de_presupuesto_no_tiene_texto_roto():
    """Un aviso con basura dentro es peor que no avisar: el usuario no lo entiende."""
    m = qn._mensaje_presupuesto("Ocio", 80, 12, 30, 53333.0, 16667.0, 47.0, False)
    assert "Gonees" not in m
    assert "80%" in m
    assert "12" in m


def test_el_aviso_contrasta_el_porcentaje_con_los_dias():
    """El aviso que vale: gastaste 80% el dia 12, no gastaste 80% y ya."""
    m = qn._mensaje_presupuesto("Ocio", 80, 12, 30, 66666.0, 33333.0, 46.7, False)
    assert "80%" in m
    assert "12" in m
    assert "30" in m
    # Y debe decir cuanto queda para corregirlo.
    assert "18 días" in m or "18 dias" in m


def test_el_aviso_de_excedido_no_promete_ajuste_de_mes_vencido():
    m = qn._mensaje_presupuesto("Comida", 130, 28, 30, 92857.0, 33333.0, 60.0, True)
    assert "130%" in m or "30 puntos" in m
    assert "ya no queda mes" in m or "no te alcanza" in m


def test_sin_datos_no_inventa_alertas():
    assert qn._mensaje({"etiqueta": "2026-10-1"}, {"ingresos": 0, "gastos": 0},
                       0.0, [], 0.0).startswith("Todav")


def test_los_mensajes_no_usan_el_formato_ingles():
    """'1,301,667' y '$1.301.667' son la misma cifra pero se leen distinta.

    El mensaje va al chat y el PDF a la mesa: si uno usa coma de miles y el otro
    punto, el usuario cree que son dos numeros distintos. Colombia separa miles
    con punto.
    """
    m = qn._mensaje({"etiqueta": "2026-10-Q1"}, {"ingresos": 0, "gastos": 1301667.0},
                    1301666.67, [], 50000.0)
    assert "$1.301.667" in m, m
    assert "1,301" not in m, f"quedo formato ingles: {m}"
    assert "$50.000" in m, m

    a = qn._mensaje_presupuesto("Ocio", 80, 12, 30, 66666.0, 33333.0, 46.7, False)
    assert "66.666" in a and "33.333" in a, a
    assert "66,666" not in a, f"quedo formato ingles: {a}"


# ---------- integración: que las alertas se disparen de verdad ----------

@pytest.fixture()
def escenario():
    """Un perfil con presupuesto, gasto y fijo, para ejercitar la revision entera.

    Monta el caso que la app tiene que avisar: presupuesto de Ocio de 500.000
    con 400.000 gastados al dia 10 de un mes de 30 (van 33% del mes con 80% de la
    plata). Ademas un arriendo del dia 20, que es el que antes se perdia.
    """
    from datetime import date as _date
    from datetime import datetime

    from app.core.database import SessionLocal
    from app.models.finance import Account, Budget, Category, Transaction
    from app.models.perfil import Perfil
    from app.models.user import User

    db = SessionLocal()
    marca = str(datetime.utcnow().timestamp())
    u = User(nombre="Quincena", correo="quincena_%s@example.com" % marca,
             password_hash="x", moneda="COP", plan="pro")
    db.add(u)
    db.commit()
    db.refresh(u)
    p = Perfil(user_id=u.id, nombre="Personal", tipo="personal", principal=True)
    db.add(p)
    db.commit()
    db.refresh(p)

    hoy = _date.today()
    cat = Category(user_id=u.id, perfil_id=p.id, nombre="Ocio", tipo="gasto")
    db.add(cat)
    db.commit()
    db.refresh(cat)

    db.add(Budget(user_id=u.id, perfil_id=p.id, categoria_id=cat.id,
                  monto=500000, periodo=hoy.strftime("%Y-%m")))
    # cuenta_id es NOT NULL en la base: sin cuenta no hay movimiento.
    cta = Account(user_id=u.id, perfil_id=p.id, nombre="Efectivo", tipo="efectivo",
                  saldo_inicial=0)
    db.add(cta)
    db.commit()
    db.refresh(cta)
    db.add(Transaction(user_id=u.id, perfil_id=p.id, cuenta_id=cta.id, tipo="gasto",
                       categoria_id=cat.id, monto=400000, descripcion="Salidas", fecha=hoy))
    db.commit()
    yield db, u, p, cat, hoy
    from app.models.goals import Recurring

    # Los recurrentes se borran aqui tambien: si un test falla antes de su
    # finally, un arriendo huerfano rompe el teardown con violation de FK.
    db.query(Transaction).filter_by(user_id=u.id).delete()
    db.query(Budget).filter_by(user_id=u.id).delete()
    db.query(Recurring).filter_by(user_id=u.id).delete()
    db.query(Category).filter_by(user_id=u.id).delete()
    db.query(Account).filter_by(user_id=u.id).delete()
    db.delete(p)
    db.delete(u)
    db.commit()
    db.close()


def test_la_alerta_de_ritmo_se_dispara(escenario):
    """El aviso que vale: 400.000 de 500.000 gastados y apenas queda parte del mes."""
    db, u, p, cat, hoy = escenario
    alertas = qn.alertas_presupuesto(db, u.id, p.id, hoy)
    assert len(alertas) == 1, "debria avisar: 80% gastado con el mes a medias"
    a = alertas[0]
    assert a["categoria"] == "Ocio"
    assert a["porcentaje"] == 80.0
    assert a["dias_transcurridos"] == hoy.day
    assert a["dias_periodo"] in (28, 29, 30, 31)
    # El presupuesto es de 500.000 en 30 dias: unos 16.667/dia sustainable.
    assert a["ritmo_sostenible"] > 0
    assert a["delta_puntos"] > 0
    assert "Ocio" in a["mensaje"]
    assert "%" in a["mensaje"]


def test_el_ritmo_se_contrasta_con_los_dias_y_no_solo_con_el_porcentaje(escenario):
    """Gastar 80% es distinto gastarlo el dia 5 que el dia 28.

    Por eso el delta se mide contra el calendario, no contra el 100%.
    """
    db, u, p, cat, hoy = escenario
    from datetime import date as _date

    inicio_de_mes = _date(hoy.year, hoy.month, 1)
    a = qn.alertas_presupuesto(db, u.id, p.id, inicio_de_mes)[0]
    b = qn.alertas_presupuesto(db, u.id, p.id, hoy)[0]
    # Mismo gasto, mismo porcentaje, distinta severidad segun el dia.
    assert a["porcentaje"] == b["porcentaje"]
    if inicio_de_mes.day < hoy.day:
        assert a["delta_puntos"] > b["delta_puntos"], \
            "al inicio de mes el desvio tiene que ser mas grave que al final"


def test_el_fijo_del_dia_20_cae_en_la_segunda_quincena_y_no_en_la_primera(escenario):
    """El arriendo del dia 20 es de la segunda quincena.

    Antes esto estaba mal y el efecto era invisible: el fijo del dia 20 no se
    sumaba en ninguna parte, y el usuario se enteraba de que le faltaba plata
    cuando ya no le quedaba.
    """
    from app.models.goals import Recurring

    db, u, p, cat, hoy = escenario
    db.add(Recurring(user_id=u.id, perfil_id=p.id, nombre="Arriendo", tipo="gasto",
                     monto=1200000, dia=20, frecuencia="mensual", activo=True))
    db.commit()
    try:
        from datetime import date as _date

        d1 = _date(hoy.year, hoy.month, 3)
        d2 = _date(hoy.year, hoy.month, 20)

        r1 = qn.revision(db, u.id, p.id, d1)
        assert r1["fijos"]["total"] == 0, "en la primera quincena no vence ese arriendo"
        assert not any(i["nombre"] == "Arriendo" for i in r1["fijos"]["items"])

        r2 = qn.revision(db, u.id, p.id, d2)
        assert r2["fijos"]["total"] == 1200000
        assert r2["fijos"]["gastos"] == 1200000
        assert [i["nombre"] for i in r2["fijos"]["items"]] == ["Arriendo"]
        assert r2["fijos"]["items"][0]["veces"] == 1
    finally:
        db.query(Recurring).filter_by(user_id=u.id).delete()
        db.commit()


def test_sin_recurrentes_no_se_inventan_fijos(escenario):
    """Cero recurrentes, cero fijos. Ni una suposicion."""
    db, u, p, cat, hoy = escenario
    from datetime import date as _date

    r = qn.revision(db, u.id, p.id, _date(hoy.year, hoy.month, 20))
    assert r["fijos"]["total"] == 0
    assert r["fijos"]["items"] == []