"""Análisis documental con la Responses API de OpenAI.

Porta src/utils/openaiService.js. La diferencia de fondo: la clave vive en el
servidor. En la versión React viajaba al navegador, donde cualquiera con las
herramientas de desarrollo podía leerla.
"""

# Importamos las librerias necesarias
import base64  # Para incrustar imágenes y PDFs en la petición
import io  # Para leer los archivos desde memoria
import json  # Para parsear la respuesta del modelo
import re  # Para limpiar la respuesta y aplicar plantillas
from datetime import date  # Para la fecha que verifica vigencias
from typing import Any, Dict, List, Optional  # Tipos

import httpx  # Cliente HTTP asíncrono

from app.core import http  # Cliente HTTP que no espera a IPv6
from app.core.config import settings  # Clave y modelo configurados
from app.core.logging import get_logger  # Para registrar fallos
from app.services.file_extract import ExtractedFile, get_extension  # Archivos ya extraídos
from app.services.openai_config import MODELOS_IA_POR_ID  # Límites y modo elegible

# Creamos el logger de este módulo
logger = get_logger(__name__)

# Definimos el endpoint de la Responses API
API_URL = "https://api.openai.com/v1/responses"

# El límite de salida forma parte de cada modelo. Ajustarlo evita que elegir un
# modelo válido produzca un 400 por pedir más tokens de los que admite.
MAX_OUTPUT_POR_MODELO = {
    modelo: datos["max_output"] for modelo, datos in MODELOS_IA_POR_ID.items()
}

# Definimos qué extensiones sabemos convertir a un bloque que el modelo entienda
SUPPORTED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".pdf", ".docx", ".xlsx", ".xls", ".xlsm", ".csv", ".txt",
}

# Definimos los meses en español para formatear la fecha sin depender del locale
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


# Definimos el error que lanzamos cuando OpenAI falla
class AnalysisError(Exception):
    """La llamada a OpenAI falló o devolvió algo inutilizable."""


# Devolvemos la fecha de hoy en el formato que usan los prompts
def _fecha_actual() -> str:
    # Tomamos la fecha del sistema
    hoy = date.today()

    # Componemos el formato largo en español
    return f"{hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"


# Sustituimos los marcadores {{VARIABLE}} de una plantilla
def apply_template(template: str, variables: Dict[str, Any]) -> str:
    # Reemplazamos cada marcador por su valor, dejando intacto el que no exista
    def _replace(match: re.Match) -> str:
        # Tomamos el nombre de la variable capturada
        key = match.group(1)

        # Devolvemos el valor si lo tenemos, o el marcador original si no
        return str(variables[key]) if key in variables else match.group(0)

    # Aplicamos la sustitución sobre toda la plantilla
    return re.sub(r"\{\{(\w+)\}\}", _replace, template)


# Convertimos un nombre a Title Case: "JUAN PEREZ" -> "Juan Perez"
def to_title_case(value: str) -> str:
    # Un valor vacío se devuelve tal cual
    if not value:
        return value

    # Pasamos a minúsculas y capitalizamos cada palabra
    return " ".join(word.capitalize() for word in value.lower().split()).strip()


# Quitamos los backticks de markdown que el modelo a veces agrega
def clean_json_response(text: str) -> str:
    # Eliminamos las vallas de código y recortamos los espacios
    return re.sub(r"```(?:json)?", "", text).strip()


# Convertimos un archivo extraído en un bloque de contenido para el modelo
def _file_to_content_block(item: ExtractedFile) -> Optional[Dict[str, Any]]:
    # Obtenemos la extensión sin el punto
    ext = get_extension(item.name)

    # Intentamos la conversión, avisando en el propio contenido si falla
    try:
        # Las imágenes viajan como data URL
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            # jpg y jpeg comparten el mismo tipo MIME
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext.lstrip('.')}"

            # Codificamos el contenido en base64
            encoded = base64.b64encode(item.content).decode("ascii")

            # Devolvemos el bloque de imagen
            return {"type": "input_image", "image_url": f"data:{mime};base64,{encoded}"}

        # Los PDF los lee el propio modelo, sin extraer texto localmente
        if ext == ".pdf":
            # Codificamos el contenido en base64
            encoded = base64.b64encode(item.content).decode("ascii")

            # Devolvemos el bloque de archivo
            return {
                "type": "input_file",
                "filename": item.name,
                "file_data": f"data:application/pdf;base64,{encoded}",
            }

        # Word se convierte a texto plano
        if ext == ".docx":
            # Devolvemos el texto extraído
            return {"type": "input_text", "text": _docx_to_text(item)}

        # Excel se convierte a tablas de texto
        if ext in (".xlsx", ".xls", ".xlsm"):
            # Devolvemos las hojas serializadas
            return {"type": "input_text", "text": _excel_to_text(item)}

        # Los archivos de texto se mandan tal cual
        if ext in (".csv", ".txt"):
            # Decodificamos tolerando bytes inválidos
            text = item.content.decode("utf-8", errors="replace")

            # Devolvemos el bloque de texto rotulado
            return {"type": "input_text", "text": f"=== ARCHIVO: {item.name} ===\n{text}"}

    # Un archivo ilegible se reporta al modelo en vez de desaparecer
    except Exception as exc:
        # Registramos el fallo para poder diagnosticarlo
        logger.warning(f"No se pudo convertir {item.name}: {exc}")

        # Devolvemos un aviso explícito dentro del propio contenido
        return {
            "type": "input_text",
            "text": (
                f"=== ARCHIVO: {item.name} (ERROR AL PROCESAR: {exc}) ===\n"
                "El archivo existe pero no se pudo leer correctamente."
            ),
        }

    # Una extensión no soportada no produce bloque
    return None


# Extraemos el texto de un .docx
def _docx_to_text(item: ExtractedFile) -> str:
    # Importamos aquí para no cargar la librería si no hay documentos Word
    from docx import Document

    # Abrimos el documento desde memoria
    document = Document(io.BytesIO(item.content))

    # Recogemos los párrafos con contenido
    partes = [p.text for p in document.paragraphs if p.text.strip()]

    # Recogemos también el contenido de las tablas, que es donde suelen ir los datos
    for tabla in document.tables:
        # Recorremos cada fila
        for fila in tabla.rows:
            # Unimos las celdas con separador de columna
            celdas = [celda.text.strip() for celda in fila.cells]

            # Descartamos las filas completamente vacías
            if any(celdas):
                partes.append(" | ".join(celdas))

    # Componemos el bloque rotulado
    cuerpo = "\n".join(partes) if partes else "(sin texto extraíble)"

    # Devolvemos el texto con su encabezado
    return f"=== DOCUMENTO WORD: {item.name} ===\n{cuerpo}"


# Convertimos un Excel a texto legible, una tabla por hoja
def _excel_to_text(item: ExtractedFile) -> str:
    # Importamos aquí para no cargar la librería si no hay hojas de cálculo
    from openpyxl import load_workbook

    # Abrimos el libro en modo solo lectura, con los valores ya calculados
    libro = load_workbook(io.BytesIO(item.content), read_only=True, data_only=True)

    # Empezamos el bloque con el nombre del archivo
    partes = [f"=== ARCHIVO EXCEL: {item.name} ==="]

    # Recorremos cada hoja
    for hoja in libro.worksheets:
        # Acumulamos las filas con contenido
        filas = []

        # Recorremos las filas de la hoja
        for fila in hoja.iter_rows(values_only=True):
            # Convertimos cada celda a texto, dejando vacías las nulas
            celdas = ["" if celda is None else str(celda) for celda in fila]

            # Descartamos las filas completamente vacías
            if any(celda.strip() for celda in celdas):
                filas.append(" | ".join(celdas))

        # Solo incluimos la hoja si aportó algo
        if filas:
            # Agregamos el encabezado de hoja y sus filas
            partes.append(f"\n--- Hoja: {hoja.title} ---")
            partes.extend(filas)

    # Cerramos el libro para liberar el archivo
    libro.close()

    # Devolvemos el bloque completo
    return "\n".join(partes)


# Normalizamos un veredicto suelto a uno de los tres valores válidos
def normalize_verdict(value: Any) -> str:
    # Pasamos a mayúsculas y recortamos
    v = str(value).upper().strip()

    # Reconocemos las variantes afirmativas
    if "APROB" in v or v in ("OK", "PASS", "YES", "SÍ", "SI"):
        return "APROBADO"

    # Reconocemos las variantes negativas
    if "RECHAZ" in v or v in ("FAIL", "NO", "REJECT"):
        return "RECHAZADO"

    # Todo lo demás queda pendiente
    return "PENDIENTE"


# Normalizamos el checklist devuelto por el modelo a una forma estable
def normalize_checklist(raw: str, expected_questions: List[str]) -> Dict[str, Any]:
    # Parseamos el JSON, tolerando los backticks de markdown
    try:
        # Limpiamos y parseamos
        parsed = json.loads(clean_json_response(raw))
    # Una respuesta no parseable es un fallo del análisis
    except json.JSONDecodeError as exc:
        # Lanzamos un error con contexto para el log
        raise AnalysisError(f"La respuesta del modelo no es JSON válido: {exc}") from exc

    # El modelo puede nombrar la lista de varias formas; probamos las conocidas
    people = (
        parsed.get("personas")
        or parsed.get("persons")
        or parsed.get("people")
        or parsed.get("results")
        or parsed.get("evaluaciones")
        or []
    )

    # Si devolvió una lista plana de resultados, la envolvemos en una persona genérica
    if people and isinstance(people[0], dict) and "pregunta" in people[0] and "resultados" not in people[0]:
        people = [{"nombre": "Evaluación General", "resultados": people}]

    # Si no quedó una lista, la tratamos como vacía
    if not isinstance(people, list):
        people = []

    # Normalizamos cada persona
    normalizadas = []

    # Recorremos la lista devuelta
    for p in people:
        # Ignoramos entradas que no sean diccionarios
        if not isinstance(p, dict):
            continue

        # Tomamos el nombre de cualquiera de las claves posibles
        name = to_title_case(
            p.get("nombre") or p.get("name") or p.get("persona") or p.get("person") or "Sin nombre"
        )

        # Tomamos los resultados de cualquiera de las claves posibles
        crudos = p.get("resultados") or p.get("results") or p.get("checklist") or p.get("items") or []

        # Normalizamos cada resultado a la misma forma
        results = [
            {
                "pregunta": r.get("pregunta") or r.get("question") or r.get("item") or "",
                "resultado": normalize_verdict(
                    r.get("resultado") or r.get("result") or r.get("status") or r.get("estado") or "PENDIENTE"
                ),
                "explicacion": (
                    r.get("explicacion") or r.get("explanation") or r.get("detalle")
                    or r.get("detail") or r.get("observacion") or ""
                ),
            }
            for r in crudos
            if isinstance(r, dict)
        ]

        # Completamos las preguntas que el modelo haya omitido
        if len(results) < len(expected_questions):
            # Indexamos lo que ya vino, normalizando para comparar
            presentes = {r["pregunta"].lower().strip() for r in results}

            # Agregamos como pendientes las que falten
            for pregunta in expected_questions:
                # Solo si no estaba ya respondida
                if pregunta.lower().strip() not in presentes:
                    # La marcamos explícitamente como no evaluada
                    results.append({
                        "pregunta": pregunta,
                        "resultado": "PENDIENTE",
                        "explicacion": "No evaluado por la IA — documento no encontrado o no analizado.",
                    })

        # Guardamos la persona ya normalizada
        normalizadas.append({"nombre": name, "resultados": results})

    # Devolvemos la estructura estable
    return {"personas": normalizadas}


# Calculamos el veredicto general a partir del checklist normalizado
def compute_overall_verdict(checklist_data: Dict[str, Any]) -> str:
    # Aplanamos todos los resultados de todas las personas
    todos = [r for p in checklist_data.get("personas", []) for r in p.get("resultados", [])]

    # Un solo rechazo tumba la solicitud completa
    if any(r["resultado"] == "RECHAZADO" for r in todos):
        return "RECHAZADO"

    # Un pendiente deja la solicitud en espera
    if any(r["resultado"] == "PENDIENTE" for r in todos):
        return "PENDIENTE"

    # Sin resultados no podemos afirmar que esté aprobado
    if not todos:
        return "PENDIENTE"

    # Todo aprobado
    return "APROBADO"


# Definimos el prompt por defecto, editable desde la pantalla de Prompts
DEFAULT_INSTRUCTIONS = """Eres un analista QHSE senior de OIG Perú especializado en verificación de permisos de acceso.

FECHA ACTUAL: {{FECHA_ACTUAL}}
TIPO DE CASO: {{CASO}}
REMITENTE: {{REMITENTE}}
ASUNTO: {{ASUNTO}}

Se te han enviado EXACTAMENTE {{NUM_ARCHIVOS}} archivos adjuntos. Están listados a continuación:
{{LISTA_ARCHIVOS}}

REGLA ABSOLUTA: Debes leer y analizar los {{NUM_ARCHIVOS}} archivos. No puedes ignorar ni omitir ninguno.

━━━ FASE 1: LECTURA DE ARCHIVOS ━━━
Revisa cada archivo de la lista uno por uno:
- Si hay un Anexo A, planilla Excel o lista de personal: extrae TODOS los nombres, sin excepción.
- Si un SCTR o seguro grupal cubre múltiples personas: identifica a TODAS las personas cubiertas.
- Cada imagen de DNI, brevete o carnet corresponde a UNA persona específica.
- Registra mentalmente: nombre completo, tipo de documento, número, fechas de vencimiento y vigencia.
- Nombres en Title Case (ej: "Juan Pérez García"). Nunca en mayúsculas completas.

━━━ FASE 2: VALIDAR CHECKLIST ━━━
Para CADA persona identificada, evalúa las {{NUM_PREGUNTAS}} preguntas del checklist:
- APROBADO: el documento existe, está vigente al {{FECHA_ACTUAL}} y cumple el requisito.
- RECHAZADO: el documento existe pero está vencido, reprobado o presenta inconsistencias.
- PENDIENTE: no se encontró evidencia del documento para esa persona.
- Si hay documentos grupales (ej: SCTR grupal), aplica el resultado a todas las personas cubiertas.
- Usa datos concretos en las explicaciones (números, fechas, aseguradora, categoría, etc.).
- Cada persona DEBE tener EXACTAMENTE {{NUM_PREGUNTAS}} resultados en su array.
- El campo "pregunta" debe ser el texto EXACTO de la pregunta del checklist, sin modificaciones.

━━━ FASE 3: RESUMEN EJECUTIVO ━━━
Basándote en los resultados de la validación, redacta el campo "resumen" en Markdown:

## Resumen Ejecutivo de Validación Documental
**Tipo de caso:** {{CASO}}
**Remitente:** {{REMITENTE}}
**Asunto:** {{ASUNTO}}
**Fecha de evaluación:** {{FECHA_ACTUAL}}
**Total personas evaluadas:** N

---
## Tabla Resumen
| N° | Nombre Completo | Aprobados | Pendientes | Rechazados | Veredicto |
|----|-----------------|-----------|------------|------------|-----------|
[una fila por persona]

---
## Detalle por Persona
[Para cada persona:]
### N. Nombre Completo
- **Veredicto:** APROBADO/RECHAZADO/PENDIENTE
- **Aprobados ✅:** [items aprobados con datos específicos]
- **Pendientes ⚠️:** [items pendientes con qué falta]
- **Rechazados ❌:** [items rechazados con motivo, o "Ninguno"]

---
## Estadísticas Generales
- **Total personas evaluadas:** N
- **Requisitos aprobados:** X
- **Requisitos pendientes:** X
- **Requisitos rechazados:** X

---
## Veredicto General
**APROBADO/RECHAZADO/PENDIENTE**
[2-3 oraciones de justificación]

---
## Acciones Requeridas
[Lista numerada de acciones concretas. Si todo aprobado: "No se requieren acciones."]

━━━ FORMATO DE RESPUESTA ━━━
Responde SOLO con JSON válido — sin backticks, sin texto antes o después:
{
  "personas": [
    {
      "nombre": "Apellidos Nombres",
      "resultados": [
        {
          "pregunta": "texto exacto del checklist",
          "resultado": "APROBADO",
          "explicacion": "dato concreto"
        }
      ]
    }
  ],
  "resumen": "## Resumen Ejecutivo de Validación Documental\\n\\n..."
}"""


# Llamamos a la Responses API y devolvemos el texto de salida
async def _responses_call(
    instructions: str,
    content: List[Dict[str, Any]],
    max_tokens: int = 128000,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    # Sin clave configurada no tiene sentido intentar la llamada
    clave = (api_key or settings.OPENAI_API_KEY).strip()
    if not clave:
        raise AnalysisError("No hay OPENAI_API_KEY configurada en el servidor")

    # Armamos el cuerpo de la petición
    modelo = model or settings.OPENAI_MODEL
    datos_modelo = MODELOS_IA_POR_ID.get(modelo, {})
    payload = {
        "model": modelo,
        "instructions": instructions,
        "input": [{"role": "user", "content": content}],
        "max_output_tokens": min(
            max_tokens, MAX_OUTPUT_POR_MODELO.get(modelo, max_tokens)
        ),
    }

    # Las familias recientes permiten desactivar por completo el razonamiento.
    # Al declararlo evitamos que el valor predeterminado cambie entre modelos.
    if datos_modelo.get("reasoning_effort"):
        payload["reasoning"] = {"effort": datos_modelo["reasoning_effort"]}
    else:
        payload["temperature"] = 0.05

    # El análisis de muchos documentos puede tardar varios minutos
    timeout = httpx.Timeout(600.0, connect=30.0)

    # Hacemos la llamada. El cliente es compartido y NO se cierra aqui: con
    # `async with` se cerraria al terminar esta llamada y la siguiente tendria
    # que montar otra vez el contexto TLS, que en este entorno cuesta 38 s.
    client = http.cliente_async()

    # Enviamos la petición autenticada, con el plazo propio de esta llamada
    response = await client.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {clave}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )

    # Un error de la API se convierte en un fallo de análisis con mensaje útil
    if response.status_code != 200:
        # Intentamos extraer el mensaje que devuelve OpenAI
        try:
            # El error viene anidado bajo la clave error
            detail = response.json().get("error", {}).get("message", "")
        # Si no es JSON, usamos el texto crudo recortado
        except Exception:
            detail = response.text[:300]

        # Registramos el fallo completo para diagnóstico
        logger.error(f"OpenAI respondió {response.status_code}: {detail}")

        # En la interfaz hablamos del servicio de IA sin exponer el proveedor.
        if re.search(r"context window|maximum context length", detail, flags=re.I):
            mensaje_usuario = (
                f"Los documentos superan la ventana de contexto de {modelo}. "
                "Reduce la cantidad de archivos o divide la solicitud en varios análisis."
            )
        else:
            mensaje_usuario = re.sub(r"openai", "IA", detail, flags=re.I)
        raise AnalysisError(mensaje_usuario or f"La IA devolvió {response.status_code}")

    # Extraemos el texto del primer mensaje de salida
    data = response.json()

    # Buscamos el bloque de tipo message dentro de output
    for bloque in data.get("output", []):
        # Solo nos interesa el mensaje, no los eventos de razonamiento
        if bloque.get("type") == "message":
            # Dentro del mensaje buscamos el texto de salida
            for parte in bloque.get("content", []):
                # Devolvemos el primer texto que encontremos
                if parte.get("type") == "output_text":
                    return parte.get("text", "")

    # Sin texto de salida no hay nada que normalizar
    raise AnalysisError("La IA no devolvió texto de salida")


# Ejecutamos el análisis completo: checklist y resumen en una sola llamada
async def validate_and_summarize(
    files: List[ExtractedFile],
    checklist: List[str],
    email_data: Any,
    case_name: str,
    custom_prompt: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    # Separamos lo que sabemos convertir de lo que no
    soportados = [f for f in files if get_extension(f.name) in SUPPORTED_EXTENSIONS]
    no_soportados = [f.name for f in files if get_extension(f.name) not in SUPPORTED_EXTENSIONS]

    # Sin archivos convertibles no hay nada que analizar
    if not soportados:
        raise AnalysisError("Ninguno de los archivos tiene un formato que la IA pueda leer")

    # Armamos la lista numerada que se inyecta en el prompt
    lista_archivos = "\n".join(f"  {i + 1}. {f.name}" for i, f in enumerate(soportados))

    # Componemos las instrucciones, permitiendo la plantilla personalizada
    instrucciones = apply_template(
        custom_prompt or DEFAULT_INSTRUCTIONS,
        {
            "FECHA_ACTUAL": _fecha_actual(),
            "NUM_ARCHIVOS": len(soportados),
            "LISTA_ARCHIVOS": lista_archivos,
            "NUM_PREGUNTAS": len(checklist),
            "CASO": case_name,
            "REMITENTE": getattr(email_data, "sender", "N/A"),
            "ASUNTO": getattr(email_data, "subject", "Sin asunto"),
        },
    )

    # Empezamos el contenido con la lista explícita, para que el modelo no omita archivos
    content: List[Dict[str, Any]] = [{
        "type": "input_text",
        "text": (
            f"Debes analizar TODOS los siguientes {len(soportados)} archivos. "
            f"No omitas ninguno:\n{lista_archivos}\n\nA continuación recibirás cada archivo:"
        ),
    }]

    # Contamos cuántos se convirtieron y cuántos fallaron
    procesados = 0
    fallidos = 0

    # Agregamos cada archivo precedido de su rótulo
    for i, item in enumerate(soportados):
        # Rotulamos para que el modelo sepa dónde empieza cada archivo
        content.append({
            "type": "input_text",
            "text": f"\n--- ARCHIVO {i + 1}/{len(soportados)}: {item.name} ---",
        })

        # Convertimos el archivo a un bloque
        bloque = _file_to_content_block(item)

        # Si se pudo convertir, lo sumamos
        if bloque is not None:
            content.append(bloque)
            procesados += 1

        # Si no, dejamos constancia visible para el modelo
        else:
            content.append({
                "type": "input_text",
                "text": f'[AVISO: El archivo "{item.name}" no pudo convertirse a un formato legible.]',
            })
            fallidos += 1

    # Componemos el bloque de cierre con el checklist y los datos del correo
    checklist_text = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(checklist))

    # Anotamos los formatos que quedaron fuera
    omitidos = f" ({len(no_soportados)} de formato no soportado omitidos: {', '.join(no_soportados)})" if no_soportados else ""

    # Agregamos el cierre
    content.append({
        "type": "input_text",
        "text": (
            f"\n--- FIN DE ARCHIVOS ---\nHas recibido {len(soportados)} archivos en total{omitidos}.\n\n"
            f"DATOS DEL CORREO:\n"
            f"- Remitente: {getattr(email_data, 'sender', 'N/A')}\n"
            f"- Asunto: {getattr(email_data, 'subject', 'Sin asunto')}\n"
            f"- Fecha del correo: {getattr(email_data, 'date', 'N/A')}\n\n"
            f"TIPO DE CASO: {case_name}\n\n"
            f"CHECKLIST ({len(checklist)} preguntas — cada persona debe tener exactamente "
            f"{len(checklist)} resultados):\n{checklist_text}\n\n"
            f"Ahora completa las 3 fases y responde SOLO con el JSON. Nada más."
        ),
    })

    # Llamamos al modelo
    response = await _responses_call(
        instrucciones, content, api_key=api_key, model=model
    )

    # Normalizamos el checklist a una forma estable
    checklist_results = normalize_checklist(response, checklist)

    # Extraemos el resumen del mismo JSON, tolerando que falte
    resumen = ""

    # Intentamos leerlo sin romper si el JSON no trae la clave
    try:
        # Parseamos otra vez para tomar solo el resumen
        parsed = json.loads(clean_json_response(response))

        # Probamos las claves conocidas
        resumen = parsed.get("resumen") or parsed.get("summary") or parsed.get("resumen_ejecutivo") or ""
    # Si no se puede parsear, el checklist ya quedó normalizado y seguimos sin resumen
    except json.JSONDecodeError:
        # Registramos que el resumen se perdió
        logger.warning("No se pudo extraer el resumen ejecutivo de la respuesta")

    # Devolvemos todo lo que necesita la pantalla de resultados
    return {
        "checklist_results": checklist_results,
        "summary": resumen,
        "verdict": compute_overall_verdict(checklist_results),
        "processed_count": procesados,
        "failed_count": fallidos,
        "total_files": len(soportados),
        "unsupported": no_soportados,
    }
