"""Guardianes contra fallos que ya ocurrieron una vez.

Cada prueba de aquí corresponde a un fallo real encontrado en este código. No
comprueban una función: comprueban que un patrón peligroso no vuelva a
aparecer, porque los tres se manifestaron lejos de su causa y costaron más
encontrarlos que arreglarlos.

  - Una etiqueta HTML sin cerrar en el menú se tragó el `<main>` y el contenido
    de todas las pantallas apareció a media anchura.
  - Una cabecera `HX-Trigger` escrita a mano con tildes reventó la respuesta con
    UnicodeDecodeError: las cabeceras HTTP no admiten caracteres fuera de ASCII.
  - Un `db.commit()` sin try/except convertía cualquier rechazo de la base en un
    500 sin cuerpo, que con HTMX es una pantalla que no reacciona.
  - Los diálogos nativos de cada navegador rompían la coherencia visual de la
    aplicación y no respetaban su tema.

Este archivo es el mismo en las dos aplicaciones hermanas.
"""

# Importamos las librerias necesarias
import ast  # Para recorrer el codigo sin ejecutarlo
import glob  # Para encontrar los archivos
import io  # Para leerlos con codificacion explicita
import os  # Para rutas relativas legibles
import re  # Para los patrones de etiqueta

import pytest  # Para los casos con parametros

from app.web.templating import toast_header  # Lo que compone la cabecera

# La raiz del proyecto, deducida de este archivo
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Las etiquetas que siempre van pareadas
PAREADAS = ("a", "div", "form", "section", "main", "aside", "nav", "table",
            "tbody", "thead", "tr", "td", "th", "span", "details", "select",
            "button", "label", "ul", "li", "p")


# Las plantillas del proyecto
def plantillas():
    return sorted(glob.glob(os.path.join(RAIZ, "app", "templates", "**", "*.html"),
                            recursive=True))


# --------------------------------------------------- etiquetas sin cerrar

@pytest.mark.parametrize("ruta", plantillas(),
                         ids=lambda r: os.path.relpath(r, RAIZ))
def test_las_etiquetas_de_la_plantilla_balancean(ruta):
    """Una etiqueta sin cerrar se traga lo que venga detras.

    El sintoma no es un error: es contenido que aparece donde no toca. Cuando
    paso, el `<main>` quedo dentro de un `<a>` del menu y heredo su anchura.
    """
    s = io.open(ruta, encoding="utf-8").read()

    # Fuera los comentarios de Jinja y los bloques de script y estilo, que
    # pueden contener texto que parezca una etiqueta
    limpio = re.sub(r"\{#.*?#\}", "", s, flags=re.S)
    limpio = re.sub(r"<script\b.*?</script>", "", limpio, flags=re.S | re.I)
    limpio = re.sub(r"<style\b.*?</style>", "", limpio, flags=re.S | re.I)

    desbalanceadas = []

    for t in PAREADAS:
        abre = len(re.findall(rf"<{t}\b", limpio, re.I))
        cierra = len(re.findall(rf"</{t}>", limpio, re.I))

        if abre != cierra:
            desbalanceadas.append(f"<{t}>: {abre} abiertas, {cierra} cerradas")

    assert not desbalanceadas, (
        f"{os.path.relpath(ruta, RAIZ)} tiene etiquetas sin cerrar: "
        + "; ".join(desbalanceadas))


# ------------------------------------------------------- cabeceras HX-Trigger

def test_ninguna_cabecera_hx_trigger_se_escribe_a_mano():
    """La cabecera se compone con `toast_header`, nunca concatenando.

    Una cabecera HTTP no admite caracteres fuera de ASCII. Escrita a mano con
    una tilde, la respuesta muere con UnicodeDecodeError; y un mensaje con una
    comilla rompe el JSON que HTMX espera.
    """
    culpables = []

    for ruta in glob.glob(os.path.join(RAIZ, "app", "**", "*.py"), recursive=True):
        s = io.open(ruta, encoding="utf-8").read()

        for i, linea in enumerate(s.split("\n"), start=1):
            if "HX-Trigger" not in linea or linea.strip().startswith("#"):
                continue

            # La linea de asignacion debe delegar en toast_header. Se admite que
            # la llamada este en la linea siguiente, que es como cabe.
            siguientes = "\n".join(s.split("\n")[i - 1:i + 2])

            if "toast_header" not in siguientes:
                culpables.append(f"{os.path.relpath(ruta, RAIZ)}:{i}")

    assert not culpables, (
        "cabeceras HX-Trigger sin toast_header: " + ", ".join(culpables))


@pytest.mark.parametrize("mensaje", [
    "Plantilla restaurada a la versión de fábrica",
    "El caso «Personal Conductor» se eliminó",
    'Con "comillas" dentro',
    "Con emoji 📋 incluido",
    "Salto\nde línea",
])
def test_la_cabecera_soporta_cualquier_mensaje(mensaje):
    """Lo que salga de `toast_header` tiene que poder viajar en una cabecera."""
    cabecera = toast_header(mensaje)

    # Las cabeceras HTTP se codifican en latin-1. Si esto lanza, la respuesta
    # entera muere, y el sintoma aparece en el cliente, no aqui.
    cabecera.encode("latin-1")


# --------------------------------------------------------- modales propios

def test_los_modales_no_dependen_del_navegador():
    """Formularios y confirmaciones usan el componente visual de la aplicación."""
    culpables = []

    for ruta in plantillas():
        contenido = io.open(ruta, encoding="utf-8").read()

        if re.search(r"<dialog\b", contenido, re.I):
            culpables.append(os.path.relpath(ruta, RAIZ))

    app_js = io.open(
        os.path.join(RAIZ, "app", "static", "js", "app.js"),
        encoding="utf-8",
    ).read()

    # Quitamos comentarios antes de buscar llamadas; documentar confirm() no es
    # lo mismo que invocarlo.
    codigo_js = re.sub(r"/\*.*?\*/|//[^\n]*", "", app_js, flags=re.S)

    assert not re.search(
        r"\b(?:alert|confirm|prompt|showModal)\s*\(", codigo_js
    ), "app.js vuelve a usar un diálogo nativo"
    assert not culpables, "plantillas con <dialog> nativo: " + ", ".join(culpables)
    assert 'addEventListener("htmx:confirm"' in app_js
    assert "pendiente.issueRequest(true)" in app_js


def test_la_carga_de_carpetas_es_recursiva():
    """El selector y el arrastre incluyen archivos de todas las subcarpetas."""
    plantilla = io.open(
        os.path.join(RAIZ, "app", "templates", "pages", "new_request.html"),
        encoding="utf-8",
    ).read()

    assert "webkitdirectory" in plantilla
    assert 'id="browse-btn"' in plantilla
    assert 'id="browse-folder-btn"' not in plantilla
    assert 'id="upload-source-modal"' not in plantilla
    assert ">Seleccionar carpeta</button>" in plantilla
    assert "webkitGetAsEntry" in plantilla
    assert "leerDirectorio" in plantilla
    assert "file.webkitRelativePath" in plantilla
    assert 'const key = path + "|" + file.size' in plantilla


def test_el_limite_de_carga_es_100_mb_y_admite_el_valor_exacto():
    """Cien MB pasan; solo se bloquea cuando el total es mayor."""
    from app.core.config import Settings

    plantilla = io.open(
        os.path.join(RAIZ, "app", "templates", "pages", "new_request.html"),
        encoding="utf-8",
    ).read()
    servidor = io.open(
        os.path.join(RAIZ, "app", "web", "requests.py"),
        encoding="utf-8",
    ).read()

    assert Settings.model_fields["MAX_UPLOAD_MB"].default == 100
    assert "const excedido = total > maxBytes;" in plantilla
    assert "if total_bytes > settings.MAX_UPLOAD_MB * 1024 * 1024:" in servidor


def test_la_carga_de_archivos_muestra_progreso_visual():
    """Carpetas grandes informan lectura, avance y finalización."""
    plantilla = io.open(
        os.path.join(RAIZ, "app", "templates", "pages", "new_request.html"),
        encoding="utf-8",
    ).read()

    assert 'id="file-load-status"' in plantilla
    assert 'id="file-load-progress"' in plantilla
    assert 'aria-live="polite"' in plantilla
    assert 'mostrarEstadoCarga("Leyendo carpetas…"' in plantilla
    assert 'mostrarEstadoCarga("Agregando archivos…"' in plantilla
    assert 'dropzone.setAttribute("aria-busy", "true")' in plantilla
    assert 'id="upload-progress"' in plantilla
    assert 'addEventListener("htmx:xhr:progress"' in plantilla
    assert 'tituloAnalisis.textContent = "Subiendo documentos"' in plantilla


def test_los_errores_http_de_htmx_son_visibles():
    """Un 4xx/5xx se inserta en la vista y también produce un aviso flotante."""
    app_js = io.open(
        os.path.join(RAIZ, "app", "static", "js", "app.js"),
        encoding="utf-8",
    ).read()
    solicitud = io.open(
        os.path.join(RAIZ, "app", "templates", "pages", "new_request.html"),
        encoding="utf-8",
    ).read()
    servidor = io.open(
        os.path.join(RAIZ, "app", "web", "requests.py"),
        encoding="utf-8",
    ).read()

    assert 'addEventListener("htmx:beforeSwap"' in app_js
    assert "event.detail.shouldSwap = true" in app_js
    assert 'addEventListener("htmx:responseError"' in app_js
    assert 'showToast(mensaje, "error")' in app_js
    assert '"htmx:responseError", "htmx:sendError", "htmx:timeout"' in solicitud
    assert "if not openai_api_key:" in servidor
    assert "El servicio de IA no está configurado en el servidor." in servidor
    assert "ai_available=bool(openai_api_key)" in servidor
    assert "const iaDisponible" in solicitud
    assert "btnAnalizar.disabled = !iaDisponible" in solicitud


def test_openai_se_configura_sin_exponer_la_clave():
    """La credencial se cifra, no vuelve al HTML y alimenta el análisis."""
    ruta = os.path.join(RAIZ, "app", "templates", "partials", "settings_panel.html")
    plantilla = io.open(ruta, encoding="utf-8").read()
    configuracion = io.open(
        os.path.join(RAIZ, "app", "web", "settings.py"), encoding="utf-8"
    ).read()
    analisis = io.open(
        os.path.join(RAIZ, "app", "web", "requests.py"), encoding="utf-8"
    ).read()
    solicitud = io.open(
        os.path.join(RAIZ, "app", "templates", "pages", "new_request.html"),
        encoding="utf-8",
    ).read()

    assert 'type="password"' in plantilla
    assert not re.search(r'<input[^>]+name="api_key"[^>]+value=', plantilla)
    assert "cifrar(nueva)" in configuracion
    assert 'exige_tabla("global_settings", "edit")' in configuracion
    assert "obtener_clave_openai(db)" in analisis
    assert "api_key=openai_api_key" in analisis
    assert 'name="model"' in plantilla
    assert "obtener_modelo_ia(db)" in analisis
    assert "model=modelo_ia" in analisis
    assert 'class="analysis-result-zone"' in solicitud
    assert ">OpenAI<" not in plantilla
    assert "API key de OpenAI" not in plantilla


# ------------------------------------------------------- commit sin proteger

# Los que se dejan a proposito, con el motivo por el que es seguro
COMMIT_PERMITIDO = {
    # Fija el search_path al abrir la conexion: si falla, la conexion no sirve
    # para nada y el error tiene que subir tal cual
    os.path.join("app", "db", "session.py"),
}


def test_ningun_commit_queda_sin_proteger():
    """Un rechazo de la base no debe salir como un 500 sin cuerpo.

    La base valida longitudes, unicidad y formatos, y hay que asumir que a veces
    dira no. Con HTMX un 500 sin cuerpo es una pantalla que no reacciona: el
    usuario no sabe si guardo.
    """
    class Buscador(ast.NodeVisitor):
        def __init__(self):
            self.dentro_de_try = 0
            self.sueltos = []

        def visit_Try(self, nodo):
            self.dentro_de_try += 1
            self.generic_visit(nodo)
            self.dentro_de_try -= 1

        def visit_Call(self, nodo):
            f = nodo.func

            if (isinstance(f, ast.Attribute) and f.attr == "commit"
                    and not self.dentro_de_try):
                self.sueltos.append(nodo.lineno)

            self.generic_visit(nodo)

    culpables = []

    for ruta in glob.glob(os.path.join(RAIZ, "app", "**", "*.py"), recursive=True):
        rel = os.path.relpath(ruta, RAIZ)

        if rel in COMMIT_PERMITIDO:
            continue

        buscador = Buscador()
        buscador.visit(ast.parse(io.open(ruta, encoding="utf-8").read()))

        for linea in buscador.sueltos:
            culpables.append(f"{rel}:{linea}")

    assert not culpables, (
        "commit() sin try/except: " + ", ".join(culpables))
