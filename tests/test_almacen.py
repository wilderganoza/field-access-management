"""Pruebas del almacén de documentos.

Lo que se guarda aquí son DNI, licencias de conducir y pólizas de personas con
nombre y apellido. Dos cosas hay que sostener:

  - El nombre que sube el usuario NO decide dónde se escribe. Un `../` en el
    nombre saldría de la carpeta del caso y pisaría la de otro.
  - La retención es de dos años, y se calcula al subir, no al consultar: si
    mañana se cambia la política, lo ya guardado conserva su plazo original.

Las llamadas de red no se prueban aquí —eso se verificó contra el bucket real—;
esto es la lógica que decide rutas, huellas y plazos.
"""

# Importamos las librerias necesarias
from datetime import datetime, timezone  # Para comprobar el plazo

import pytest  # Para los casos con parámetros

from app.services import almacen  # Lo que se prueba


# ------------------------------------------------- el nombre no elige la ruta

@pytest.mark.parametrize("peligroso", [
    "../../etc/passwd",
    "..\\..\\Windows\\System32\\config",
    "/etc/shadow",
    "carpeta/otro/documento.pdf",
    "C:\\Users\\alguien\\secreto.pdf",
])
def test_un_nombre_con_ruta_se_queda_en_su_ultimo_tramo(peligroso):
    limpio = almacen.nombre_seguro(peligroso)

    # Ni barras ni saltos hacia arriba: lo que quede es un nombre, no una ruta
    assert "/" not in limpio
    assert "\\" not in limpio
    assert not limpio.startswith(".")


def test_un_nombre_normal_se_conserva():
    assert almacen.nombre_seguro("DNI - Juan Perez.pdf") == "DNI - Juan Perez.pdf"


def test_un_nombre_que_queda_vacio_recibe_uno_propio():
    # Sin esto se escribiría en la carpeta del caso con nombre vacío, y el
    # siguiente archivo sin nombre lo pisaría
    assert almacen.nombre_seguro("../") == "documento"
    assert almacen.nombre_seguro("") == "documento"
    assert almacen.nombre_seguro("...") == "documento"


def test_un_nombre_larguisimo_se_recorta():
    largo = "a" * 500 + ".pdf"

    assert len(almacen.nombre_seguro(largo)) <= 180


@pytest.mark.parametrize("raro", ["archivo\x00nulo.pdf", "doc<script>.pdf",
                                  "informe|con|tuberias.pdf"])
def test_los_caracteres_raros_se_sustituyen(raro):
    limpio = almacen.nombre_seguro(raro)

    assert all(c.isalnum() or c in "._- " for c in limpio)


# ------------------------------------------------------------------- huella

def test_el_mismo_contenido_da_la_misma_huella():
    # Es lo que permite reconocer que un mismo DNI ya está guardado
    a = almacen.huella(b"contenido identico")
    b = almacen.huella(b"contenido identico")

    assert a == b


def test_contenidos_distintos_dan_huellas_distintas():
    assert almacen.huella(b"uno") != almacen.huella(b"otro")


def test_la_huella_es_un_sha256():
    assert len(almacen.huella(b"x")) == 64


# ---------------------------------------------------------------- retención

def test_la_retencion_es_de_dos_anios():
    vence = almacen.caduca_en()
    dias = (vence - datetime.now(timezone.utc)).days

    # 730 días, con un día de margen por si se cruza la medianoche
    assert 729 <= dias <= 730


def test_el_plazo_se_declara_donde_se_lee():
    # Un número suelto en el código sería imposible de auditar
    assert almacen.RETENCION_DIAS == 730


def test_la_url_firmada_dura_poco():
    # Una URL de vida larga es una URL que se acaba filtrando
    assert almacen.VIDA_URL_FIRMADA <= 900


# ----------------------------------------------------- sin almacén no rompe

def test_sin_configurar_no_se_sube_pero_no_lanza(monkeypatch):
    # Perder el archivo es malo; no poder analizar es peor. El análisis debe
    # seguir aunque Storage no esté disponible.
    monkeypatch.setattr(almacen, "disponible", lambda: False)

    assert almacen.subir("CASO-1", "x.pdf", b"datos") is None
    assert almacen.url_firmada("CASO-1/x.pdf") is None
    assert almacen.borrar(["CASO-1/x.pdf"]) == 0


def test_sin_configurar_el_lote_devuelve_lo_que_se_pudo(monkeypatch):
    monkeypatch.setattr(almacen, "disponible", lambda: False)

    res = almacen.guardar_lote("CASO-1", [("a.pdf", b"uno"), ("b.pdf", b"dos")])

    assert len(res) == 2

    for r in res:
        # Sin ruta no hay nada que conservar, y anotar una caducidad sobre un
        # archivo inexistente solo confunde
        assert r["storage_path"] is None
        assert r["retain_until"] is None
        # La huella y el tamaño sí se conocen: se calcularon sobre los bytes
        assert r["content_hash"]
        assert r["size_bytes"] > 0


def test_borrar_una_lista_vacia_no_llama_a_nadie():
    assert almacen.borrar([]) == 0
    assert almacen.borrar([None, ""]) == 0
