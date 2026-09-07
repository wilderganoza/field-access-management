"""Configuración de Jinja2 y helpers compartidos por todas las páginas."""

# Importamos las librerias necesarias
import json  # Para serializar la cabecera de los toasts
from pathlib import Path  # Para resolver rutas del proyecto
from typing import Optional  # Para tipar el usuario opcional

import bleach  # Para sanear el HTML que produce el markdown de la IA
import markdown  # Para convertir el resumen ejecutivo a HTML
from fastapi import Request  # Para leer datos del request en el contexto
from fastapi.templating import Jinja2Templates  # Motor de plantillas
from markupsafe import Markup  # Para marcar como seguro solo lo ya saneado

from app.core.config import settings  # Nombre y versión de la app

# Resolvemos el directorio raíz del paquete app/
APP_DIR = Path(__file__).resolve().parents[1]

# Guardamos las rutas de plantillas y estáticos
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

# Creamos el motor de plantillas apuntando a app/templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# Construimos la URL de un archivo estático agregando un parámetro de versión.
# Así el navegador no sirve CSS viejo tras un despliegue, sin tener que renombrar
# los archivos ni configurar cabeceras de caché.
def asset(path: str) -> str:
    """Ruta pública del estático, con la marca de tiempo del archivo.

    Antes esto usaba la versión de la aplicación, que no cambia al editar una
    hoja de estilos: el navegador servía la copia cacheada y las correcciones de
    diseño no se veían hasta vaciar la caché a mano. Con la fecha de
    modificación, cada cambio en el archivo cambia la URL y llega solo.
    """
    completa = STATIC_DIR / path

    try:
        version = int(completa.stat().st_mtime)
    # Si el archivo no está, se cae a la versión de la aplicación: es un enlace
    # roto de todas formas, y no debe tumbar el renderizado
    except OSError:
        version = settings.APP_VERSION

    return f"/static/{path}?v={version}"


# Definimos qué etiquetas se permiten al renderizar el resumen ejecutivo.
# El markdown lo escribe el modelo a partir de documentos que sube un tercero,
# así que se trata como contenido no confiable: sin <script>, sin atributos de
# evento y sin enlaces con esquemas raros.
MARKDOWN_TAGS = [
    "p", "br", "hr", "strong", "em", "del", "code", "pre", "blockquote",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td", "a",
]

# Definimos los atributos permitidos por etiqueta
MARKDOWN_ATTRS = {"a": ["href", "title"], "th": ["align"], "td": ["align"]}


# Convertimos markdown a HTML saneado, listo para insertar en la página
def render_markdown(text: str) -> Markup:
    # Un texto vacío no produce nada
    if not text:
        return Markup("")

    # Convertimos el markdown, habilitando tablas y saltos de línea simples
    html = markdown.markdown(text, extensions=["tables", "nl2br", "sane_lists"])

    # Saneamos el resultado descartando cualquier etiqueta o atributo no permitido
    limpio = bleach.clean(
        html,
        tags=MARKDOWN_TAGS,
        attributes=MARKDOWN_ATTRS,
        protocols=["http", "https", "mailto"],
        strip=True,
    )

    # Marcamos como seguro solo después de sanear
    return Markup(limpio)


# Registramos el helper como global de Jinja para poder usarlo en las plantillas
templates.env.globals["asset"] = asset

# Los permisos, para que una plantilla pueda decidir si pinta un boton.
#
# Se importa aqui dentro y no arriba porque `permisos` importa los modelos, y
# los modelos no deben depender del motor de plantillas.
def _puede(usuario, modulo, accion="view"):
    """Cierto si ese usuario puede esa accion en ese modulo."""
    from app.services.permisos import puede

    return puede(usuario, modulo, accion)


def _ve_algo(usuario, modulo):
    """Cierto si ve el modulo o alguno de sus submodulos."""
    from app.services.permisos import ve_algo

    return ve_algo(usuario, modulo)


templates.env.globals["puede"] = _puede
templates.env.globals["ve_algo"] = _ve_algo

# Registramos el filtro de markdown, que usan las pantallas de resultados
templates.env.filters["markdown"] = render_markdown

# Exponemos el nombre de la app para el título y el header
templates.env.globals["app_name"] = settings.APP_NAME


# Armamos el contexto base que toda página necesita
def page_context(request: Request, current_user: Optional[dict] = None, **extra) -> dict:
    # Partimos del request, que Jinja2Templates exige, y del usuario actual
    context = {
        "request": request,
        "current_user": current_user,
    }

    # Sumamos lo específico de cada página
    context.update(extra)

    # Devolvemos el contexto completo
    return context

# Armamos la cabecera HX-Trigger que dispara un toast en el navegador.
#
# Va por json.dumps y no por concatenacion por dos motivos: las cabeceras HTTP
# no admiten caracteres fuera de ASCII (una vocal con tilde las corrompe), y un
# mensaje con comillas romperia el JSON. json.dumps escapa ambas cosas.
def toast_header(message: str, level: str = "success") -> str:
    # ensure_ascii deja los acentos escapados, y HTMX los vuelve a decodificar
    return json.dumps({"toast": {"message": message, "level": level}}, ensure_ascii=True)
