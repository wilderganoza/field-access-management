"""Guarda y recupera los documentos de una solicitud.

Hasta ahora los archivos se leían en memoria, se mandaban al modelo y se
descartaban: el histórico decía qué archivos hubo pero no dejaba abrir ninguno,
así que no había forma de auditar sobre qué se decidió.

Van a un bucket **privado** de Supabase Storage. Nunca se sirve una URL directa:
se firma una de vida corta cada vez que alguien pide ver un archivo. Lo que se
guarda son DNI, licencias y pólizas de personas con nombre y apellido, y una URL
pública es una URL que se acaba filtrando.

**Retención: dos años.** Y se borran con el caso, sin esperar a que venza el
plazo — no deben sobrevivir al expediente que los justificaba.
"""

# Importamos las librerias necesarias
import hashlib  # Para la huella del contenido
import re  # Para limpiar el nombre del archivo
from datetime import datetime, timedelta, timezone  # Para fechar la retención
from typing import List, Optional, Tuple  # Tipos

import httpx  # Solo para reconocer sus errores; el cliente lo da app.core.http

from app.core import http  # Cliente HTTP que no espera a IPv6
from app.core.config import settings  # URL del proyecto y clave de servicio
from app.core.logging import get_logger  # Para registrar la actividad

# Creamos el logger de este módulo
logger = get_logger(__name__)

# El bucket, privado, donde viven los documentos
BUCKET = "fda-documentos"

# Cuánto se conservan, en días. Dos años.
RETENCION_DIAS = 730

# Cuánto vive una URL firmada, en segundos. Cinco minutos basta para abrir un
# archivo y es poco para que sirva de algo si se filtra.
VIDA_URL_FIRMADA = 300

# Plazo de las llamadas al almacén
PLAZO = 60.0


# Indicamos si el almacén está configurado
def disponible() -> bool:
    """Cierto si hay con qué hablar con Storage."""
    # Sin clave de servicio la aplicación no puede subir en nombre de nadie
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)


# Componemos las cabeceras de la API de Storage
def _cabeceras(tipo: Optional[str] = None) -> dict:
    # La clave de servicio se usa aquí y solo aquí: el permiso ya se comprobó en
    # la ruta, y el navegador nunca ve esta clave
    h = {
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
    }

    if tipo:
        h["Content-Type"] = tipo

    return h


# Construimos la URL de la API de almacenamiento
def _url(sufijo: str) -> str:
    return f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1{sufijo}"


# Limpiamos el nombre para que sea una ruta válida
def nombre_seguro(nombre: str) -> str:
    """El nombre sin rutas ni caracteres que Storage rechace.

    Un nombre que venga con `../` o con barras saldría de la carpeta del caso y
    pisaría la de otro. Se quedan solo el último tramo y los caracteres
    razonables.
    """
    # Nos quedamos con el último tramo, venga con barras de Windows o de Unix
    base = re.split(r"[\\/]", nombre or "")[-1].strip()

    # Y sustituimos lo que no sea seguro en una ruta
    limpio = re.sub(r"[^A-Za-z0-9._\- ]+", "_", base).strip(". ")

    # Un nombre que se quede vacío tras limpiarlo necesita uno propio
    return limpio[:180] or "documento"


# Calculamos la huella del contenido
def huella(contenido: bytes) -> str:
    """El sha256 del archivo, para reconocer los repetidos."""
    return hashlib.sha256(contenido).hexdigest()


# Cuándo caduca la conservación de lo que se sube ahora
def caduca_en() -> datetime:
    """La fecha en la que este documento deja de conservarse."""
    return datetime.now(timezone.utc) + timedelta(days=RETENCION_DIAS)


# Subimos un archivo al bucket
def subir(analysis_id: str, nombre: str, contenido: bytes,
          tipo: str = "application/octet-stream") -> Optional[str]:
    """Sube el archivo y devuelve su ruta en el bucket, o None si no se pudo.

    La ruta es `{analysis_id}/{nombre}`: agrupada por solicitud, de modo que
    borrar un caso es borrar una carpeta.
    """
    # Sin almacén configurado no se sube, pero el análisis debe seguir: perder
    # el archivo es malo, no poder analizar es peor
    if not disponible():
        logger.warning("Storage no configurado: el documento no se conserva")
        return None

    ruta = f"{analysis_id}/{nombre_seguro(nombre)}"

    try:
        cliente = http.cliente()

        respuesta = cliente.post(
                _url(f"/object/{BUCKET}/{ruta}"),
                headers={**_cabeceras(tipo), "x-upsert": "true"},
                content=contenido,
            )

        # Un rechazo del almacén se registra con su motivo
        if respuesta.status_code not in (200, 201):
            logger.warning(
                f"No se pudo guardar «{ruta}» ({respuesta.status_code}): "
                f"{respuesta.text[:200]}")
            return None

        return ruta

    # Un fallo de red no puede tumbar el análisis entero
    except httpx.HTTPError as exc:
        logger.warning(f"Fallo de red guardando «{ruta}»: {exc}")
        return None


# Firmamos una URL temporal para ver un archivo
def url_firmada(ruta: str, segundos: int = VIDA_URL_FIRMADA) -> Optional[str]:
    """Una URL que sirve el archivo durante unos minutos, o None."""
    if not disponible() or not ruta:
        return None

    try:
        cliente = http.cliente()

        respuesta = cliente.post(
                _url(f"/object/sign/{BUCKET}/{ruta}"),
                headers=_cabeceras("application/json"),
                json={"expiresIn": segundos},
            )

        if respuesta.status_code != 200:
            logger.info(f"No se pudo firmar «{ruta}» ({respuesta.status_code})")
            return None

        # La API devuelve la ruta firmada relativa a /storage/v1
        firmada = (respuesta.json() or {}).get("signedURL", "")

        if not firmada:
            return None

        return f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1{firmada}"

    except httpx.HTTPError as exc:
        logger.info(f"Fallo de red firmando «{ruta}»: {exc}")
        return None


# Borramos archivos del bucket
def borrar(rutas: List[str]) -> int:
    """Borra esas rutas y devuelve cuántas se pudieron borrar.

    Se llama al eliminar un caso: los documentos no sobreviven al expediente que
    los justificaba. Se hace por la API y no borrando filas de `storage.objects`
    para que el archivo desaparezca de verdad del almacén, no solo del índice.
    """
    limpias = [r for r in rutas if r]

    if not limpias or not disponible():
        return 0

    try:
        cliente = http.cliente()

        respuesta = cliente.request(
                "DELETE",
                _url(f"/object/{BUCKET}"),
                headers=_cabeceras("application/json"),
                json={"prefixes": limpias},
            )

        if respuesta.status_code != 200:
            logger.warning(
                f"No se pudieron borrar {len(limpias)} documento(s) "
                f"({respuesta.status_code}): {respuesta.text[:200]}")
            return 0

        logger.info(f"Borrados {len(limpias)} documento(s) del almacén")

        return len(limpias)

    except httpx.HTTPError as exc:
        logger.warning(f"Fallo de red borrando documentos: {exc}")
        return 0


# Guardamos de una vez los archivos de una solicitud
def guardar_lote(analysis_id: str,
                 archivos: List[Tuple[str, bytes]]) -> List[dict]:
    """Sube todos y devuelve, por archivo, lo que hay que anotar en la base.

    Cada elemento trae `name`, `storage_path`, `size_bytes`, `content_hash` y
    `retain_until`, listos para escribir en `analysis_files`.
    """
    vence = caduca_en()
    resultado = []

    for nombre, contenido in archivos:
        ruta = subir(analysis_id, nombre, contenido)

        resultado.append({
            "name": nombre,
            "storage_path": ruta,
            "size_bytes": len(contenido),
            "content_hash": huella(contenido),
            # Si no se pudo subir no hay nada que conservar, y anotar una fecha
            # de caducidad sobre un archivo inexistente solo confunde
            "retain_until": vence if ruta else None,
        })

    guardados = sum(1 for r in resultado if r["storage_path"])

    logger.info(f"Solicitud {analysis_id}: {guardados}/{len(archivos)} documento(s) conservados")

    return resultado
