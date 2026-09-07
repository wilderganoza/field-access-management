"""Edición de la plantilla de prompt que guía el análisis documental."""

# Importamos las librerias necesarias
from fastapi import APIRouter, Depends, Form, Request  # Router y formularios
from fastapi.responses import HTMLResponse  # Respuestas HTML
from sqlalchemy.orm import Session  # Sesión de base de datos

from app.core.errores import motivo_de_base  # Rechazos de la base, legibles
from app.core.deps import exige_tabla  # Exige el permiso del perfil sobre la tabla
from app.core.logging import get_logger  # Para registrar los cambios
from app.db.session import get_db  # Dependencia de sesión
from app.models.analysis import PromptTemplate  # Modelo
from app.services.openai_service import DEFAULT_INSTRUCTIONS  # Plantilla de fábrica
from app.web.templating import page_context, templates, toast_header  # Plantillas

# Creamos el logger de este módulo
logger = get_logger(__name__)

# Creamos el router de prompts
router = APIRouter(prefix="/prompts")

# Definimos el identificador de la única plantilla que usa el análisis
PROMPT_ID = "validate_and_summarize"

# Documentamos las variables que el análisis sustituye en la plantilla,
# para que quien la edite sepa con qué cuenta.
VARIABLES = [
    ("FECHA_ACTUAL", "Fecha de hoy en texto, para verificar vigencias"),
    ("CASO", "Nombre del caso de validación elegido"),
    ("REMITENTE", "Dirección de correo que envió la solicitud"),
    ("ASUNTO", "Asunto del correo"),
    ("NUM_ARCHIVOS", "Cantidad de archivos que recibe la IA"),
    ("LISTA_ARCHIVOS", "Lista numerada de los nombres de archivo"),
    ("NUM_PREGUNTAS", "Cantidad de preguntas del checklist"),
]


# Mostramos el editor de la plantilla
@router.get("", response_class=HTMLResponse)
def prompts(
    request: Request,
    current_user: dict = Depends(exige_tabla("prompt_templates", "view")),
    db: Session = Depends(get_db),
):
    # Buscamos la plantilla personalizada
    template_row = db.query(PromptTemplate).filter(PromptTemplate.id == PROMPT_ID).first()

    # Renderizamos el editor, cayendo a la de fábrica si nunca se editó
    return templates.TemplateResponse(
        "pages/prompts.html",
        page_context(
            request,
            current_user=current_user,
            content=template_row.content if template_row else DEFAULT_INSTRUCTIONS,
            is_custom=template_row is not None,
            updated_at=template_row.updated_at if template_row else None,
            variables=VARIABLES,
        ),
    )


# Guardamos la plantilla editada
@router.post("", response_class=HTMLResponse)
def save(
    request: Request,
    content: str = Form(...),
    current_user: dict = Depends(exige_tabla("prompt_templates", "edit")),
    db: Session = Depends(get_db),
):
    # Una plantilla vacía dejaría el análisis sin instrucciones
    if not content.strip():
        # Devolvemos el error
        return templates.TemplateResponse(
            "partials/error_message.html",
            page_context(request, current_user=current_user,
                         message="La plantilla no puede quedar vacía."),
            status_code=400,
        )

    # Buscamos la plantilla existente
    template_row = db.query(PromptTemplate).filter(PromptTemplate.id == PROMPT_ID).first()

    # La creamos si es la primera edición
    if template_row is None:
        # Insertamos el registro
        template_row = PromptTemplate(id=PROMPT_ID, content=content)
        db.add(template_row)

    # O actualizamos la que había
    else:
        # Reemplazamos el contenido
        template_row.content = content

    # Confirmamos
    try:
        db.commit()

    except Exception as exc:
        db.rollback()
        logger.warning(f"No se pudo guardar la plantilla: {exc}")

        return templates.TemplateResponse(
            "partials/error_message.html",
            page_context(request, current_user=current_user,
                         message=motivo_de_base(exc, "plantilla")),
            status_code=409,
        )

    # Registramos quién la cambió: afecta a todos los análisis siguientes
    logger.info(f"Plantilla de prompt actualizada por {current_user['email']}")

    # Devolvemos la confirmación
    response = templates.TemplateResponse(
        "partials/prompt_saved.html",
        page_context(request, current_user=current_user),
    )

    # Avisamos con un toast
    response.headers["HX-Trigger"] = toast_header("Plantilla guardada", "success")

    # Devolvemos la respuesta
    return response


# Restauramos la plantilla de fábrica
@router.post("/reset", response_class=HTMLResponse)
def reset(
    request: Request,
    current_user: dict = Depends(exige_tabla("prompt_templates", "edit")),
    db: Session = Depends(get_db),
):
    # Borramos la personalización, si la había
    try:
        db.query(PromptTemplate).filter(PromptTemplate.id == PROMPT_ID).delete()
        db.commit()

    # Si no se pudo, hay que decirlo: devolver la plantilla de fabrica en
    # pantalla mientras la personalizada sigue guardada seria mentir
    except Exception as exc:
        db.rollback()
        logger.warning(f"No se pudo restaurar la plantilla: {exc}")

        return templates.TemplateResponse(
            "partials/error_message.html",
            page_context(request, current_user=current_user,
                         message="No se pudo restaurar la plantilla de fábrica."),
            status_code=409,
        )

    # Registramos la restauración
    logger.info(f"Plantilla de prompt restaurada a la de fábrica por {current_user['email']}")

    # Devolvemos el editor con el contenido de fábrica
    response = templates.TemplateResponse(
        "partials/prompt_editor.html",
        page_context(
            request,
            current_user=current_user,
            content=DEFAULT_INSTRUCTIONS,
            is_custom=False,
            updated_at=None,
            variables=VARIABLES,
        ),
    )

    # Por toast_header, no concatenando: una cabecera HTTP no admite caracteres
    # fuera de ASCII, y «versión de fábrica» escrito a pelo llegaba con bytes
    # latin-1 crudos que reventaban la respuesta con UnicodeDecodeError.
    # `toast_header` los escapa y HTMX los vuelve a decodificar.
    response.headers["HX-Trigger"] = toast_header(
        "Plantilla restaurada a la versión de fábrica")

    # Devolvemos la respuesta
    return response
