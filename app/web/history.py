"""Historial de solicitudes procesadas: listado, filtros y borrado."""

# Importamos las librerias necesarias

from fastapi import APIRouter, Depends, Request  # Router y dependencias
from fastapi.responses import HTMLResponse, RedirectResponse, Response  # Respuestas
from sqlalchemy import or_  # Para el filtro de búsqueda libre
from sqlalchemy.orm import Session  # Sesión de base de datos

from app.core.deps import exige_tabla  # Exige el permiso del perfil sobre la tabla
from app.core.logging import get_logger  # Para registrar borrados
from app.db.session import get_db  # Dependencia de sesión
from app.services import almacen  # Documentos en el bucket privado
from app.models.analysis import AnalysisFile, AnalysisHistory, Case  # Modelos
from app.web.templating import page_context, templates, toast_header  # Plantillas

# Creamos el logger de este módulo
logger = get_logger(__name__)

# Creamos el router del historial
router = APIRouter(prefix="/history")


# Construimos la consulta aplicando los filtros recibidos
def _query_history(db: Session, case_filter: str, verdict: str, search: str):
    # Partimos del historial completo, ordenado por fecha descendente.
    # Nota: se muestran las solicitudes de todos los operadores, igual que en la
    # versión anterior. Es un equipo de cumplimiento y necesitan verse entre sí.
    query = db.query(AnalysisHistory)

    # Filtramos por caso si se eligió uno
    if case_filter:
        query = query.filter(AnalysisHistory.case_id == case_filter)

    # Filtramos por veredicto si se eligió uno
    if verdict:
        query = query.filter(AnalysisHistory.verdict == verdict)

    # Filtramos por texto libre sobre nombre, asunto y remitente
    if search:
        # Envolvemos el término en comodines
        pattern = f"%{search.strip()}%"

        # Buscamos en los tres campos que el operador reconoce
        query = query.filter(or_(
            AnalysisHistory.request_name.ilike(pattern),
            AnalysisHistory.email_subject.ilike(pattern),
            AnalysisHistory.email_from.ilike(pattern),
        ))

    # Devolvemos la consulta ordenada
    return query.order_by(AnalysisHistory.created_at.desc())


# Mostramos la pantalla de historial
@router.get("", response_class=HTMLResponse)
def history(
    request: Request,
    case_filter: str = "",
    verdict: str = "",
    search: str = "",
    current_user: dict = Depends(exige_tabla("analysis_history", "view")),
    db: Session = Depends(get_db),
):
    # Aplicamos los filtros
    records = _query_history(db, case_filter, verdict, search).all()

    # Cargamos los casos para el selector de filtro
    cases = db.query(Case).order_by(Case.name).all()

    # Si la petición viene de HTMX, devolvemos solo la tabla
    template_row = (
        "partials/history_table.html"
        if request.headers.get("HX-Request") == "true"
        else "pages/history.html"
    )

    # Renderizamos
    return templates.TemplateResponse(
        template_row,
        page_context(
            request,
            current_user=current_user,
            records=records,
            cases=cases,
            filter_case=case_filter,
            filter_verdict=verdict,
            filter_search=search,
        ),
    )


# Eliminamos una solicitud del historial
@router.delete("/{analysis_id}")
def delete(
    analysis_id: str,
    current_user: dict = Depends(exige_tabla("analysis_history", "delete")),
    db: Session = Depends(get_db),
):
    # Buscamos el registro
    record = db.query(AnalysisHistory).filter(AnalysisHistory.id == analysis_id).first()

    # Si no existe, avisamos con 404
    if record is None:
        # Devolvemos vacío con el código correspondiente
        return Response(status_code=404)

    # Los documentos se borran ANTES de perder sus rutas: la cascada de la base
    # se lleva las filas de `analysis_files`, y con ellas la unica referencia a
    # donde vive cada archivo. Borrar primero la fila dejaria el documento
    # huerfano en el bucket para siempre.
    #
    # Es la politica acordada: dos anios de retencion, pero se borran con el
    # caso sin esperar al plazo -- son documentos de identidad y no deben
    # sobrevivir al expediente que los justificaba.
    rutas = [f.storage_path for f in record.files if f.storage_path]

    if rutas:
        almacen.borrar(rutas)

    # Borramos; la cascada se lleva archivos y resultados
    try:
        db.delete(record)
        db.commit()

    # Algo puede referenciar la solicitud: se dice, no se devuelve un 500
    except Exception as exc:
        db.rollback()
        logger.warning(f"No se pudo eliminar el historial {analysis_id}: {exc}")

        return Response(status_code=409)

    # Registramos quién borró qué, que en cumplimiento importa
    logger.info(f"Historial {analysis_id} eliminado por {current_user['email']}")

    # Devolvemos vacío: HTMX quita la fila del DOM con hx-swap="outerHTML"
    response = Response(status_code=200)

    # Disparamos el aviso flotante desde el servidor
    response.headers["HX-Trigger"] = toast_header("Solicitud eliminada", "success")

    # Devolvemos la respuesta
    return response


# Servimos un documento conservado.
#
# No se devuelve el archivo por aqui: se firma una URL de vida corta contra el
# bucket privado y se redirige. Asi los bytes no pasan por esta aplicacion y la
# direccion deja de servir a los pocos minutos, que es lo que evita que un
# enlace copiado siga abriendo un DNI meses despues.
@router.get("/files/{file_id}")
def documento(
    file_id: int,
    current_user: dict = Depends(exige_tabla("analysis_files", "download")),
    db: Session = Depends(get_db),
):
    fila = db.query(AnalysisFile).filter(AnalysisFile.id == file_id).first()

    # Un archivo que no existe, o que nunca llego a conservarse
    if fila is None or not fila.storage_path:
        return Response(status_code=404)

    url = almacen.url_firmada(fila.storage_path)

    # Si el almacen no responde se dice, en vez de mandar a una URL rota
    if url is None:
        return Response(status_code=502)

    logger.info(f"{current_user['email']} abrio el documento {fila.name} "
                f"de la solicitud {fila.analysis_id}")

    return RedirectResponse(url, status_code=307)
