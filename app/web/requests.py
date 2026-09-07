"""Flujo principal: cargar documentos, analizarlos y mostrar el resultado."""

# Importamos las librerias necesarias
import uuid  # Para generar el identificador de cada solicitud
from typing import List, Optional  # Tipos

from fastapi import APIRouter, Depends, Form, Request, UploadFile  # Router y formularios
from fastapi.responses import HTMLResponse  # Respuestas HTML
from sqlalchemy.orm import Session  # Sesión de base de datos

from app.core.config import settings  # Límite de tamaño de subida
from app.core.deps import exige_tabla  # Exige el permiso del perfil sobre la tabla
from app.core.logging import get_logger  # Para registrar el avance
from app.db.session import get_db  # Dependencia de sesión
from app.models.analysis import (  # Modelos del dominio
    AnalysisChecklistResult, AnalysisFile, AnalysisHistory, Case, PromptTemplate,
)
from app.services import almacen  # Documentos en el bucket privado
from app.services.file_extract import process_uploads  # Extracción de archivos
from app.services.openai_config import (  # Credencial y modelo editables
    obtener_clave_openai, obtener_modelo_ia,
)
from app.services.openai_service import AnalysisError, validate_and_summarize  # Análisis
from app.web.templating import page_context, templates  # Plantillas

# Creamos el logger de este módulo
logger = get_logger(__name__)

# Lo minimo que se admite como nombre de solicitud. Un caracter suelto pasa
# cualquier comprobacion de «no vacio» y no identifica nada.
LARGO_MINIMO_NOMBRE = 3


# Cuanto se lee de una vez al recibir un archivo
TROZO_LECTURA = 1024 * 1024


# Creamos el router del flujo principal
router = APIRouter()


# Devolvemos los casos disponibles con su checklist ya cargado
def _load_cases(db: Session) -> List[Case]:
    # Ordenamos por nombre para que la lista sea estable
    return db.query(Case).order_by(Case.name).all()


# Mostramos la pantalla de carga de documentos
@router.get("/", response_class=HTMLResponse)
def new_request(
    request: Request,
    current_user: dict = Depends(exige_tabla("analysis_history", "view")),
    db: Session = Depends(get_db),
):
    # Cargamos los casos para el selector
    cases = _load_cases(db)
    openai_api_key = obtener_clave_openai(db)

    # Renderizamos la pantalla
    return templates.TemplateResponse(
        "pages/new_request.html",
        page_context(
            request,
            current_user=current_user,
            cases=cases,
            max_upload_mb=settings.MAX_UPLOAD_MB,
            ai_available=bool(openai_api_key),
        ),
    )


# Procesamos la solicitud: extraemos, analizamos y guardamos
@router.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    files: List[UploadFile] = Form(default=[]),
    case_id: str = Form(...),
    request_name: str = Form(""),
    current_user: dict = Depends(exige_tabla("analysis_history", "create")),
    db: Session = Depends(get_db),
):
    # Verificamos que el caso exista antes de gastar una llamada al modelo
    case: Optional[Case] = db.query(Case).filter(Case.id == case_id).first()

    # Un caso inexistente es un error del formulario
    if case is None:
        # Devolvemos el fragmento de error para que HTMX lo inserte
        return templates.TemplateResponse(
            "partials/error_message.html",
            page_context(request, current_user=current_user,
                         message="El caso seleccionado ya no existe."),
            status_code=400,
        )

    # El nombre lo pone quien crea la solicitud, siempre.
    #
    # Antes era opcional y, si venia vacio, se tomaba el asunto del correo. Eso
    # dejaba el historial lleno de «RV: Fwd: documentacion» y de nombres
    # repetidos, que es justo lo que hace inservible una busqueda. Se comprueba
    # ANTES de leer los archivos: no tiene sentido subir hasta el límite y analizarlos
    # para rechazar la solicitud despues por el nombre.
    nombre = (request_name or "").strip()
    openai_api_key = obtener_clave_openai(db)
    modelo_ia = obtener_modelo_ia(db)

    if not nombre:
        return templates.TemplateResponse(
            "partials/error_message.html",
            page_context(request, current_user=current_user,
                         message="Ponle un nombre a la solicitud."),
            status_code=400,
        )

    if len(nombre) < LARGO_MINIMO_NOMBRE:
        return templates.TemplateResponse(
            "partials/error_message.html",
            page_context(request, current_user=current_user,
                         message=f"El nombre debe tener al menos {LARGO_MINIMO_NOMBRE} caracteres."),
            status_code=400,
        )

    # Fallamos antes de leer y expandir decenas de archivos si el proveedor no
    # está configurado. La causa técnica queda en el log; el usuario recibe una
    # indicación clara y puede reintentar después de configurar el servicio.
    if not openai_api_key:
        logger.error(
            "Analisis rechazado antes de procesar archivos: falta OPENAI_API_KEY"
        )
        return templates.TemplateResponse(
            "partials/error_message.html",
            page_context(
                request,
                current_user=current_user,
                message=(
                    "El servicio de IA no está configurado en el servidor. "
                    "Contacta al administrador antes de volver a intentarlo."
                ),
            ),
            status_code=503,
        )

    # Leemos el contenido de cada archivo subido
    uploads = []

    # Acumulamos el peso total para respetar el límite configurado
    total_bytes = 0

    # Recorremos los archivos del formulario
    for upload in files:
        # Ignoramos las entradas vacías que manda el navegador
        if not upload.filename:
            continue

        # Leemos por trozos, comprobando el limite a cada uno.
        #
        # Antes esto hacia `await upload.read()`, que trae el archivo entero a
        # memoria, y solo DESPUES miraba el tamaño. El comentario decia «en vez
        # de agotar la memoria del servidor», pero para cuando se comprobaba ya
        # estaba agotada: un unico archivo de varios GB tumbaba el proceso antes
        # de llegar a la condicion. Leyendo a trozos se corta en cuanto se pasa.
        trozos = []
        pasado = False

        while True:
            trozo = await upload.read(TROZO_LECTURA)

            # Sin mas datos, este archivo termino
            if not trozo:
                break

            total_bytes += len(trozo)

            # En cuanto se pasa se deja de leer: no se acumula lo que sobra
            if total_bytes > settings.MAX_UPLOAD_MB * 1024 * 1024:
                pasado = True
                break

            trozos.append(trozo)

        # Cortamos si se paso del límite, en vez de agotar la memoria del servidor
        if pasado:
            # Devolvemos el error indicando el límite
            return templates.TemplateResponse(
                "partials/error_message.html",
                page_context(request, current_user=current_user,
                             message=f"La solicitud supera el límite de {settings.MAX_UPLOAD_MB} MB."),
                status_code=413,
            )

        # Solo ahora se junta: hacerlo antes de comprobar el limite significaba
        # copiar hasta el límite configurado para tirarlos acto seguido
        content = b"".join(trozos)

        # Guardamos el par nombre/contenido
        uploads.append((upload.filename, content))

    # Sin archivos no hay nada que analizar
    if not uploads:
        # Devolvemos el error correspondiente
        return templates.TemplateResponse(
            "partials/error_message.html",
            page_context(request, current_user=current_user,
                         message="Agrega al menos un archivo para analizar."),
            status_code=400,
        )

    # Expandimos comprimidos y correos
    extracted = process_uploads(uploads)

    # Recuperamos los archivos finales y los datos del correo
    final_files = extracted["files"]
    email_data = extracted["email"]
    warnings = extracted["warnings"]

    # Si tras expandir no quedó nada analizable, avisamos con el detalle
    if not final_files:
        # Componemos el mensaje incluyendo los avisos de la extracción
        detail = " ".join(warnings) if warnings else "No se encontraron documentos analizables."

        # Devolvemos el error
        return templates.TemplateResponse(
            "partials/error_message.html",
            page_context(request, current_user=current_user, message=detail),
            status_code=400,
        )

    # Cargamos el checklist del caso, en orden
    checklist = [item.question for item in case.checklist]

    # Cargamos la plantilla personalizada si el equipo la editó
    template_row = db.query(PromptTemplate).filter(
        PromptTemplate.id == "validate_and_summarize"
    ).first()

    # Registramos el arranque del análisis
    logger.info(
        f"Analizando {len(final_files)} archivos para el caso {case.id} "
        f"(usuario {current_user['email']})"
    )

    # Ejecutamos el análisis
    try:
        # Llamamos al servicio, que hace una sola llamada al modelo
        result = await validate_and_summarize(
            files=final_files,
            checklist=checklist,
            email_data=email_data,
            case_name=case.name,
            custom_prompt=template_row.content if template_row else None,
            api_key=openai_api_key,
            model=modelo_ia,
        )
    # Un fallo del modelo se muestra al usuario en vez de romper la pantalla
    except AnalysisError as exc:
        # Registramos el fallo con contexto
        logger.error(f"Fallo el analisis del caso {case.id}: {exc}")

        # Devolvemos el fragmento de error
        mensaje = str(exc)
        if "OPENAI_API_KEY" in mensaje:
            mensaje = (
                "El servicio de IA no está configurado en el servidor. "
                "Contacta al administrador antes de volver a intentarlo."
            )

        return templates.TemplateResponse(
            "partials/error_message.html",
            page_context(request, current_user=current_user, message=mensaje),
            status_code=502,
        )

    # Generamos el identificador de la solicitud
    analysis_id = uuid.uuid4().hex

    # Guardamos la cabecera del análisis, copiando los datos del caso
    record = AnalysisHistory(
        id=analysis_id,
        user_id=current_user["id"],
        request_name=nombre,
        case_id=case.id,
        case_name=case.name,
        case_icon=case.icon,
        case_color=case.color,
        email_from=email_data.sender,
        email_to=email_data.to,
        email_subject=email_data.subject,
        email_date=email_data.date,
        email_body=email_data.body[:20000],
        summary=result["summary"],
        verdict=result["verdict"],
    )

    # Lo agregamos a la sesión
    db.add(record)

    # Guardamos los archivos analizados, y los archivos mismos.
    #
    # Antes aqui solo se anotaba el nombre: los bytes se descartaban y el
    # historial decia QUE archivos hubo sin dejar abrir ninguno, de modo que no
    # habia forma de auditar sobre que se decidio. Ahora van a un bucket privado
    # con dos anios de retencion, y se borran con el caso.
    conservados = almacen.guardar_lote(
        analysis_id, [(f.name, f.content) for f in final_files])

    # Se indexa por nombre para casar cada archivo con lo que se guardo de el
    por_nombre = {c["name"]: c for c in conservados}

    for item in final_files:
        guardado = por_nombre.get(item.name, {})

        # Registramos cada archivo con su extensión y donde quedo guardado
        db.add(AnalysisFile(
            analysis_id=analysis_id,
            name=item.name,
            file_type=item.extension.lstrip(".") or "desconocido",
            # Si el almacen no estaba disponible el analisis sigue, pero se
            # distingue: «leido» es que se analizo, «conservado» es que ademas
            # se puede volver a abrir
            status="conservado" if guardado.get("storage_path") else "leido",
            storage_path=guardado.get("storage_path"),
            size_bytes=guardado.get("size_bytes"),
            content_hash=guardado.get("content_hash"),
            retain_until=guardado.get("retain_until"),
        ))

    # Guardamos cada resultado del checklist
    for persona in result["checklist_results"]["personas"]:
        # Recorremos sus resultados
        for r in persona["resultados"]:
            # Registramos la fila
            db.add(AnalysisChecklistResult(
                analysis_id=analysis_id,
                person_name=persona["nombre"],
                question=r["pregunta"],
                result=r["resultado"],
                explanation=r["explicacion"],
            ))

    # Confirmamos la transacción completa.
    #
    # Este analisis ya costo una llamada al modelo: si la escritura falla hay
    # que decirlo, no devolver un 500 que deja al usuario sin saber si su
    # solicitud quedo registrada.
    try:
        db.commit()

    except Exception as exc:
        db.rollback()
        logger.error(f"No se pudo guardar el analisis {analysis_id}: {exc}")

        return templates.TemplateResponse(
            "partials/error_message.html",
            page_context(request, current_user=current_user,
                         message="El análisis se completó pero no se pudo guardar. "
                                 "Vuelve a intentarlo."),
            status_code=409,
        )

    # Registramos el cierre
    logger.info(f"Analisis {analysis_id} completado: {result['verdict']}")

    # Devolvemos el fragmento que redirige a los resultados.
    # HX-Redirect hace que el navegador navegue de verdad, para que la URL
    # quede compartible en vez de dejar el resultado dentro de la pantalla de carga.
    response = HTMLResponse("")
    response.headers["HX-Redirect"] = f"/results/{analysis_id}"
    return response


# Mostramos el resultado de una solicitud ya analizada
@router.get("/results/{analysis_id}", response_class=HTMLResponse)
def results(
    analysis_id: str,
    request: Request,
    current_user: dict = Depends(exige_tabla("analysis_history", "view")),
    db: Session = Depends(get_db),
):
    # Buscamos la solicitud
    record = db.query(AnalysisHistory).filter(AnalysisHistory.id == analysis_id).first()

    # Si no existe, mostramos la pantalla de no encontrado
    if record is None:
        # Devolvemos 404 con una página legible
        return templates.TemplateResponse(
            "pages/not_found.html",
            page_context(request, current_user=current_user),
            status_code=404,
        )

    # Agrupamos los resultados por persona, conservando el orden de inserción
    people: dict = {}

    # Recorremos los resultados guardados
    for r in record.results:
        # Creamos la entrada de la persona la primera vez que aparece
        people.setdefault(r.person_name, []).append(r)

    # Renderizamos la pantalla de resultados
    return templates.TemplateResponse(
        "pages/results.html",
        page_context(
            request,
            current_user=current_user,
            record=record,
            people=people,
        ),
    )
