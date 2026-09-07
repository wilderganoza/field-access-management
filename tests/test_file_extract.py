"""Pruebas de la expansión de lo que el usuario sube.

FDA acepta archivos sueltos, comprimidos y correos, y lo que llega al análisis no
es lo que se subió: un .zip se abre, un .eml aporta sus adjuntos y sus cabeceras,
y por el camino se descartan los temporales de Office. Ese paso decide qué ve el
modelo, así que si se rompe, el análisis se hace sobre otra cosa sin que nadie lo
note.

No hace falta base de datos: todo esto es lógica pura sobre bytes en memoria.
"""

# Importamos las librerias necesarias
import io  # Para construir los archivos en memoria
import sys  # Para simular el lector RAR sin depender de un binario en la prueba
import types  # Para construir el módulo RAR simulado
import zipfile  # Para armar los comprimidos de prueba

from app.services.file_extract import (  # Funciones a probar
    _extract_rar, get_extension, is_temp_file, parse_eml, process_uploads,
)


# Construimos un zip en memoria con el contenido que se le pase
def hacer_zip(entradas: dict) -> bytes:
    """Devuelve los bytes de un zip con {nombre: contenido}."""
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w") as z:
        for nombre, contenido in entradas.items():
            z.writestr(nombre, contenido)

    return buffer.getvalue()


# Construimos un correo mínimo con un adjunto
def hacer_eml(asunto: str, remitente: str, adjunto: tuple = None) -> bytes:
    """Devuelve los bytes de un .eml, con adjunto si se pide."""
    from email.message import EmailMessage

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = remitente
    mensaje["To"] = "destino@oig.com.pe"
    mensaje.set_content("Cuerpo del correo.")

    # El adjunto llega como (nombre, contenido)
    if adjunto is not None:
        nombre, contenido = adjunto
        mensaje.add_attachment(contenido, maintype="application",
                               subtype="octet-stream", filename=nombre)

    return mensaje.as_bytes()


# ------------------------------------------------------------------ extensión

# Comprobamos que la extensión sale normalizada
def test_la_extension_va_en_minusculas_y_con_punto():
    # Da igual cómo la escriba quien sube el archivo
    assert get_extension("Permiso.PDF") == ".pdf"
    assert get_extension("informe.docx") == ".docx"


# Y que un archivo sin extensión no inventa una
def test_sin_extension_devuelve_cadena_vacia():
    # No hay punto, así que no hay extensión
    assert get_extension("LEEME") == ""


# ------------------------------------------------------------------ temporales

# Comprobamos que se reconocen los temporales de Office
def test_reconoce_los_temporales_de_office():
    # Word y Excel dejan estos al abrir un documento
    assert is_temp_file("~$permiso.docx")


# Y los ocultos de sistema
def test_reconoce_los_ocultos():
    # Los que empiezan por punto
    assert is_temp_file(".DS_Store")


# Lo importante: se mira el nombre, no la ruta dentro del comprimido
def test_el_temporal_se_reconoce_dentro_de_una_carpeta():
    # Un zip guarda la ruta completa, y mirar la cadena entera fallaría
    assert is_temp_file("carpeta/subcarpeta/~$permiso.docx")
    assert is_temp_file("carpeta\\~$permiso.docx")


# Y un archivo normal no se descarta por llevar un punto en medio
def test_un_nombre_normal_no_es_temporal():
    # El punto del medio no lo convierte en oculto
    assert not is_temp_file("permiso.v2.pdf")
    assert not is_temp_file("carpeta/permiso.pdf")


# ---------------------------------------------------------------------- correo

# Comprobamos que del correo se sacan las cabeceras
def test_del_correo_se_sacan_asunto_y_remitente():
    # Un correo sin adjuntos, solo por sus cabeceras
    datos = parse_eml(hacer_eml("Solicitud de permiso", "obra@oig.com.pe"))

    # El asunto y el remitente son lo que la pantalla muestra arriba
    assert "Solicitud de permiso" in (datos.subject or "")
    assert "obra@oig.com.pe" in (datos.sender or "")


# Y que sus adjuntos se recuperan
def test_del_correo_se_sacan_los_adjuntos():
    # Un correo con un PDF dentro
    datos = parse_eml(hacer_eml("Con adjunto", "obra@oig.com.pe",
                                ("permiso.pdf", b"%PDF-1.4 contenido")))

    # El adjunto tiene que aparecer, o el análisis se haría sin él
    nombres = [a.name for a in datos.attachments]
    assert any(n.endswith("permiso.pdf") for n in nombres)


# ------------------------------------------------------------------ el conjunto

# Comprobamos que un archivo suelto pasa tal cual
def test_un_archivo_suelto_pasa_sin_tocar():
    # Lo que se sube es lo que se analiza
    resultado = process_uploads([("permiso.pdf", b"%PDF-1.4 contenido")])

    assert len(resultado["files"]) == 1
    assert resultado["files"][0].name.endswith("permiso.pdf")


# El selector de carpetas también entrega los temporales que deja Office
def test_un_temporal_suelto_se_descarta():
    resultado = process_uploads([
        ("Ejemplo/~$Anexo.xlsx", b"temporal"),
        ("Ejemplo/Anexo.xlsx", b"documento real"),
    ])

    assert [archivo.name for archivo in resultado["files"]] == ["Ejemplo/Anexo.xlsx"]


# Comprobamos que un zip se abre
def test_el_zip_se_expande():
    # Dos documentos dentro de un comprimido
    z = hacer_zip({"permiso.pdf": b"%PDF-1.4 uno",
                   "anexo.pdf": b"%PDF-1.4 dos"})

    resultado = process_uploads([("adjuntos.zip", z)])

    # Salen los dos, no el comprimido
    nombres = [f.name for f in resultado["files"]]
    assert len(nombres) == 2
    assert not any(n.endswith(".zip") for n in nombres)


def test_los_zip_anidados_se_expanden_en_varios_niveles():
    interior = hacer_zip({"nivel-4/permiso.pdf": b"%PDF-1.4 profundo"})
    for nivel in range(3, 0, -1):
        interior = hacer_zip({f"nivel-{nivel}/contenedor.zip": interior})

    resultado = process_uploads([("raiz.zip", interior)])

    assert [archivo.name for archivo in resultado["files"]] == [
        "nivel-4/permiso.pdf"
    ]
    assert "contenedor.zip" in resultado["files"][0].origin


def test_un_zip_adjunto_a_un_correo_tambien_se_expande():
    comprimido = hacer_zip({"documentos/permiso.pdf": b"%PDF-1.4 adjunto"})
    correo = hacer_eml("Solicitud", "obra@oig.com.pe", ("documentos.zip", comprimido))

    resultado = process_uploads([("correo.eml", correo)])

    assert [archivo.name for archivo in resultado["files"]] == [
        "documentos/permiso.pdf"
    ]


def test_un_rar_puede_contener_un_zip_anidado(monkeypatch):
    comprimido = hacer_zip({"carpeta/permiso.pdf": b"%PDF-1.4 desde rar"})

    class Info:
        filename = "interior.zip"
        file_size = len(comprimido)

        @staticmethod
        def is_dir():
            return False

    class ArchivoRar:
        def __init__(self, _contenido):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def infolist():
            return [Info()]

        @staticmethod
        def read(_info):
            return comprimido

    modulo = types.SimpleNamespace(RarFile=ArchivoRar, BSDTAR_TOOL="bsdtar")
    monkeypatch.setitem(sys.modules, "rarfile", modulo)

    extraidos, error = _extract_rar(b"rar simulado", "documentos.rar")

    assert error is None
    assert [archivo.name for archivo in extraidos] == ["carpeta/permiso.pdf"]


# Y que al expandirlo se descartan los temporales
def test_el_zip_descarta_los_temporales():
    # Word dejó su temporal dentro del comprimido
    z = hacer_zip({"permiso.pdf": b"%PDF-1.4 uno",
                   "~$permiso.docx": b"basura"})

    resultado = process_uploads([("adjuntos.zip", z)])

    # Solo queda el documento de verdad
    nombres = [f.name for f in resultado["files"]]
    assert len(nombres) == 1
    assert nombres[0].endswith("permiso.pdf")


# Comprobamos que un zip corrupto avisa en vez de romper
def test_un_zip_corrupto_avisa_y_no_rompe():
    # Bytes que no son un zip
    resultado = process_uploads([("roto.zip", b"esto no es un zip")])

    # No se cae, y se dice que algo pasó
    assert resultado["files"] == []
    assert resultado["warnings"]


# Comprobamos que el correo aporta sus adjuntos al conjunto
def test_el_correo_aporta_sus_adjuntos():
    # Un .eml con un PDF dentro
    eml = hacer_eml("Solicitud", "obra@oig.com.pe",
                    ("permiso.pdf", b"%PDF-1.4 contenido"))

    resultado = process_uploads([("correo.eml", eml)])

    # El adjunto pasa al análisis
    nombres = [f.name for f in resultado["files"]]
    assert any(n.endswith("permiso.pdf") for n in nombres)

    # Y las cabeceras quedan disponibles para la pantalla
    assert "Solicitud" in (resultado["email"].subject or "")


# Y que subir varias cosas a la vez las junta todas
def test_se_juntan_varios_origenes():
    # Un suelto, un comprimido y un correo en la misma subida
    z = hacer_zip({"anexo.pdf": b"%PDF-1.4 dos"})
    eml = hacer_eml("Solicitud", "obra@oig.com.pe",
                    ("adjunto.pdf", b"%PDF-1.4 tres"))

    resultado = process_uploads([
        ("permiso.pdf", b"%PDF-1.4 uno"),
        ("adjuntos.zip", z),
        ("correo.eml", eml),
    ])

    # Los tres documentos acaban en el análisis
    nombres = [f.name for f in resultado["files"]]
    assert len(nombres) == 3


# Y que no subir nada no revienta
def test_sin_archivos_no_revienta():
    # El formulario puede llegar vacío
    resultado = process_uploads([])

    assert resultado["files"] == []

    # Se devuelve un correo vacio, no un nulo: la pantalla lee sus campos
    # sin comprobar antes si hay correo
    assert resultado["email"].subject == "Sin asunto"
    assert resultado["email"].attachments == []
