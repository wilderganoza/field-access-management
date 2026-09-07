"""Gestión de casos de validación y su checklist."""

# Importamos las librerias necesarias
import time  # Para generar identificadores de casos nuevos
from typing import List  # Tipos

from fastapi import APIRouter, Depends, Form, Request  # Router y formularios
from fastapi.responses import HTMLResponse, Response  # Respuestas
from sqlalchemy.orm import Session  # Sesión de base de datos

from app.core.errores import motivo_de_base  # Rechazos de la base, legibles
from app.core.deps import exige_tabla  # Exige el permiso del perfil sobre la tabla
from app.core.logging import get_logger  # Para registrar los cambios
from app.db.session import get_db  # Dependencia de sesión
from app.models.analysis import AnalysisHistory, Case, CaseChecklistItem  # Modelos
from app.web.templating import page_context, templates, toast_header  # Plantillas

# Creamos el logger de este módulo
logger = get_logger(__name__)

# Creamos el router de casos
router = APIRouter(prefix="/cases")


# Cargamos los casos en el orden que espera la interfaz
def _load_cases(db: Session) -> List[Case]:
    # Primero los que vienen de fábrica, después los propios por antigüedad
    return db.query(Case).order_by(Case.is_default.desc(), Case.created_at.asc()).all()


# Devolvemos el fragmento con la lista completa de casos
def _list_response(request: Request, current_user: dict, db: Session, status_code: int = 200):
    # Renderizamos solo el bloque de la lista, que es lo que HTMX reemplaza
    return templates.TemplateResponse(
        "partials/cases_list.html",
        page_context(request, current_user=current_user, cases=_load_cases(db)),
        status_code=status_code,
    )


# Limpiamos las preguntas recibidas del formulario
def _clean_checklist(questions: List[str]) -> List[str]:
    # Descartamos las vacías, que aparecen cuando el usuario deja filas en blanco
    return [p.strip() for p in questions if p and p.strip()]


# Devolvemos un error dentro del fragmento, sin recargar la pantalla
def _error(request: Request, current_user: dict, mensaje: str, status_code: int = 400):
    """El mismo fragmento de error que usa el resto de la aplicacion."""
    return templates.TemplateResponse(
        "partials/error_message.html",
        page_context(request, current_user=current_user, message=mensaje),
        status_code=status_code,
    )


# Mostramos la pantalla de casos
@router.get("", response_class=HTMLResponse)
def cases(
    request: Request,
    current_user: dict = Depends(exige_tabla("cases", "view")),
    db: Session = Depends(get_db),
):
    # Renderizamos la pantalla completa
    return templates.TemplateResponse(
        "pages/cases.html",
        page_context(request, current_user=current_user, cases=_load_cases(db)),
    )


# Descartamos la edición devolviendo la lista tal como está guardada
@router.get("/list", response_class=HTMLResponse)
def cases_list(
    request: Request,
    current_user: dict = Depends(exige_tabla("cases", "view")),
    db: Session = Depends(get_db),
):
    # HTMX reemplaza solo la lista; al renderizarla de nuevo se pierden los cambios
    # locales y todos los editores vuelven a quedar cerrados
    return _list_response(request, current_user, db)


# Creamos un caso nuevo
@router.post("", response_class=HTMLResponse)
def create(
    request: Request,
    name: str = Form(...),
    icon: str = Form("📋"),
    color: str = Form("#4a7cff"),
    description: str = Form(""),
    questions: List[str] = Form(default=[]),
    current_user: dict = Depends(exige_tabla("cases", "create")),
    db: Session = Depends(get_db),
):
    # Normalizamos el checklist
    checklist = _clean_checklist(questions)

    # Un caso sin preguntas no sirve para validar nada
    if not name.strip() or not checklist:
        # Devolvemos el error para que HTMX lo muestre
        return templates.TemplateResponse(
            "partials/error_message.html",
            page_context(request, current_user=current_user,
                         message="El nombre y al menos una pregunta son obligatorios."),
            status_code=400,
        )

    # Generamos un identificador legible y único
    case_id = f"CUSTOM_{int(time.time() * 1000):X}"

    # Creamos el caso
    case_filter = Case(
        id=case_id,
        name=name.strip(),
        icon=icon.strip() or "📋",
        color=color.strip() or "#4a7cff",
        description=description.strip(),
        is_default=False,
    )

    # Lo agregamos a la sesión
    db.add(case_filter)

    # Agregamos sus preguntas en orden
    for i, pregunta in enumerate(checklist, start=1):
        # Cada pregunta guarda su posición
        db.add(CaseChecklistItem(case_id=case_id, question=pregunta, sort_order=i))

    # Confirmamos. La base valida longitudes y formatos, y hay que asumir que
    # a veces dira no: un nombre pegado desde otro sitio pasa del limite de la
    # columna y antes eso salia como un 500 sin cuerpo.
    try:
        db.commit()

    except Exception as exc:
        db.rollback()
        logger.warning(f"No se pudo crear el caso: {exc}")

        return _error(request, current_user, motivo_de_base(exc, "caso"), 409)

    # Registramos el alta
    logger.info(f"Caso {case_id} creado por {current_user['email']}")

    # Devolvemos la lista actualizada
    response = _list_response(request, current_user, db, status_code=201)

    # Avisamos con un toast
    response.headers["HX-Trigger"] = toast_header("Caso creado", "success")

    # Devolvemos la respuesta
    return response


# Actualizamos un caso existente
@router.post("/{case_id}", response_class=HTMLResponse)
def update(
    case_id: str,
    request: Request,
    name: str = Form(...),
    icon: str = Form("📋"),
    color: str = Form("#4a7cff"),
    description: str = Form(""),
    questions: List[str] = Form(default=[]),
    current_user: dict = Depends(exige_tabla("cases", "edit")),
    db: Session = Depends(get_db),
):
    # Buscamos el caso
    case_filter = db.query(Case).filter(Case.id == case_id).first()

    # Si no existe, avisamos
    if case_filter is None:
        # Devolvemos el error
        return templates.TemplateResponse(
            "partials/error_message.html",
            page_context(request, current_user=current_user, message="El caso ya no existe."),
            status_code=404,
        )

    # Normalizamos el checklist
    checklist = _clean_checklist(questions)

    # Un caso sin preguntas no sirve
    if not name.strip() or not checklist:
        # Devolvemos el error
        return templates.TemplateResponse(
            "partials/error_message.html",
            page_context(request, current_user=current_user,
                         message="El nombre y al menos una pregunta son obligatorios."),
            status_code=400,
        )

    # Actualizamos los datos del caso
    case_filter.name = name.strip()
    case_filter.icon = icon.strip() or "📋"
    case_filter.color = color.strip() or "#4a7cff"
    case_filter.description = description.strip()

    # Reemplazamos el checklist completo, que es como lo edita la interfaz
    db.query(CaseChecklistItem).filter(CaseChecklistItem.case_id == case_id).delete()

    # Insertamos las preguntas nuevas en orden
    for i, pregunta in enumerate(checklist, start=1):
        # Cada pregunta guarda su posición
        db.add(CaseChecklistItem(case_id=case_id, question=pregunta, sort_order=i))

    # Confirmamos, con el mismo cuidado que en el alta
    try:
        db.commit()

    except Exception as exc:
        db.rollback()
        logger.warning(f"No se pudo actualizar el caso {case_id}: {exc}")

        return _error(request, current_user, motivo_de_base(exc, "caso"), 409)

    # Registramos el cambio
    logger.info(f"Caso {case_id} actualizado por {current_user['email']}")

    # Devolvemos la lista actualizada
    response = _list_response(request, current_user, db)

    # Avisamos con un toast
    response.headers["HX-Trigger"] = toast_header("Caso actualizado", "success")

    # Devolvemos la respuesta
    return response


# Eliminamos un caso
@router.delete("/{case_id}", response_class=HTMLResponse)
def delete(
    case_id: str,
    request: Request,
    current_user: dict = Depends(exige_tabla("cases", "delete")),
    db: Session = Depends(get_db),
):
    # Buscamos el caso
    case_filter = db.query(Case).filter(Case.id == case_id).first()

    # Si no existe, no hay nada que borrar
    if case_filter is None:
        # Devolvemos 404 vacío
        return Response(status_code=404)

    # Contamos cuántas solicitudes lo usaron. El historial copia los datos del
    # caso, así que borrarlo no rompe registros pasados, pero conviene avisar.
    usage_count = db.query(AnalysisHistory).filter(AnalysisHistory.case_id == case_id).count()

    # Borramos; la cascada se lleva el checklist
    try:
        db.delete(case_filter)
        db.commit()

    # El historial referencia el caso, asi que la base puede impedirlo
    except Exception as exc:
        db.rollback()
        logger.warning(f"No se pudo eliminar el caso {case_id}: {exc}")

        return _error(
            request, current_user,
            "No se puede eliminar: hay solicitudes que dependen de este caso.", 409)

    # Registramos la baja
    logger.info(f"Caso {case_id} eliminado por {current_user['email']} (usado en {usage_count} solicitudes)")

    # Devolvemos la lista actualizada
    response = _list_response(request, current_user, db)

    # Componemos el aviso indicando el impacto en el historial
    if usage_count:
        # Avisamos que el historial se conserva
        message = f"Caso eliminado. Las {usage_count} solicitudes que lo usaron conservan sus datos."
        level = "warning"
    else:
        # Aviso simple
        message = "Caso eliminado"
        level = "success"

    # Por toast_header, no concatenando. Dos motivos: una cabecera HTTP no
    # admite caracteres fuera de ASCII —una tilde la corrompe— y `message`
    # puede traer una comilla que rompa el JSON. json.dumps escapa ambas.
    response.headers["HX-Trigger"] = toast_header(message, level)

    # Devolvemos la respuesta
    return response
