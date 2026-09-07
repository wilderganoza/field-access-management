"""Extracción y normalización de los archivos de una solicitud.

Porta lo que antes hacía el navegador con jszip, unrar-js y postal-mime.
Moverlo al servidor tiene dos ventajas sobre la versión React: los archivos
grandes ya no pasan por la memoria del navegador, y el correo se parsea con la
librería estándar de Python en vez de una implementación de terceros.
"""

# Importamos las librerias necesarias
import email  # Parser de correos de la librería estándar
import io  # Para trabajar con los archivos en memoria
import shutil  # Para localizar el extractor de RAR disponible
import subprocess  # Para comprobar si tar.exe es realmente bsdtar
import zipfile  # Descompresión de .zip
from dataclasses import dataclass, field  # Para modelar los archivos extraídos
from email import policy  # Política moderna del parser, que decodifica cabeceras
from email.message import EmailMessage  # Tipo del correo parseado
from typing import Dict, List, Optional, Tuple  # Tipos

from app.core.logging import get_logger  # Para registrar lo que se descarta

# Creamos el logger de este módulo
logger = get_logger(__name__)

# Cuanto puede ocupar, descomprimida, una sola entrada de un contenedor
MAX_ENTRADA_BYTES = 200 * 1024 * 1024

# Y cuanto puede llegar a ocupar todo lo extraido de un mismo contenedor
MAX_EXTRAIDO_BYTES = 500 * 1024 * 1024

# Evita que millones de entradas vacías consuman CPU y memoria aunque no pesen.
MAX_ENTRADAS_COMPRIMIDAS = 5000

# Un comprimido puede contener otro, pero el recorrido no puede ser infinito.
MAX_NIVELES_COMPRIMIDOS = 8


# Definimos las extensiones que la aplicación acepta
ACCEPTED_EXTENSIONS = {
    ".eml", ".pdf", ".docx", ".doc", ".xlsx", ".xls",
    ".png", ".jpg", ".jpeg", ".zip", ".txt", ".rar", ".7z", ".7zip",
}

# Definimos qué extensiones son contenedores comprimidos
COMPRESSED_EXTENSIONS = {".zip", ".rar", ".7z", ".7zip"}

# Definimos los iconos por extensión, para mostrarlos en la lista de archivos
FILE_ICONS = {
    ".eml": "📧", ".pdf": "📄", ".docx": "📝", ".doc": "📝",
    ".xlsx": "📊", ".xls": "📊", ".png": "🖼️", ".jpg": "🖼️",
    ".jpeg": "🖼️", ".zip": "📦", ".rar": "📦", ".7z": "📦",
    ".7zip": "📦", ".txt": "📃",
}


# Modelamos un archivo ya extraído y listo para analizar
@dataclass
class ExtractedFile:
    # Guardamos el nombre visible del archivo
    name: str

    # Guardamos el contenido en memoria
    content: bytes

    # Guardamos de dónde salió: el nombre del contenedor, o "" si vino suelto
    origin: str = ""

    # Devolvemos la extensión en minúsculas, con el punto incluido
    @property
    def extension(self) -> str:
        # Partimos por el último punto del nombre
        return ("." + self.name.rsplit(".", 1)[-1].lower()) if "." in self.name else ""

    # Devolvemos el tamaño en bytes
    @property
    def size(self) -> int:
        # Medimos el contenido en memoria
        return len(self.content)

    # Devolvemos el icono correspondiente a la extensión
    @property
    def icon(self) -> str:
        # Caemos a un clip genérico si la extensión no está mapeada
        return FILE_ICONS.get(self.extension, "📎")


# Modelamos los datos que se extraen de un correo .eml
@dataclass
class EmailData:
    # Guardamos el remitente
    sender: str = "N/A"

    # Guardamos el destinatario
    to: str = "N/A"

    # Guardamos el asunto
    subject: str = "Sin asunto"

    # Guardamos la fecha declarada en el correo
    date: str = "N/A"

    # Guardamos el cuerpo en texto plano
    body: str = ""

    # Guardamos los adjuntos ya extraídos
    attachments: List[ExtractedFile] = field(default_factory=list)


# Devolvemos la extensión de un nombre de archivo
def get_extension(filename: str) -> str:
    # Normalizamos a minúsculas y anteponemos el punto
    return ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""


# Determinamos si un archivo es temporal de Office o un oculto de sistema
def is_temp_file(filename: str) -> bool:
    # Nos quedamos solo con el nombre, descartando cualquier ruta interna
    name = filename.replace("\\", "/").split("/")[-1]

    # Office deja archivos ~$ y los sistemas Unix ocultan con punto inicial
    return name.startswith("~$") or name.startswith(".")


# Determinamos si un archivo debe conservarse tras descomprimir
def _should_keep(filename: str) -> bool:
    # Descartamos temporales y extensiones que la app no sabe leer
    return not is_temp_file(filename) and get_extension(filename) in ACCEPTED_EXTENSIONS


def _normalizar_ruta(filename: str) -> str:
    """Conserva las subcarpetas sin aceptar rutas absolutas ni `..`."""
    partes = []
    for parte in filename.replace("\\", "/").split("/"):
        if parte in ("", ".", ".."):
            continue
        partes.append(parte)
    return "/".join(partes)


def _configurar_backend_rar(rarfile) -> None:
    """Permite que rarfile use el bsdtar incluido en Windows como tar.exe."""
    if shutil.which("unrar") or shutil.which("unar") or shutil.which("bsdtar"):
        return

    tar = shutil.which("tar")
    if not tar:
        return

    try:
        version = subprocess.run(
            [tar, "--version"], capture_output=True, text=True, timeout=5,
            check=False,
        ).stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return

    if "bsdtar" in version:
        rarfile.BSDTAR_TOOL = tar


# Descomprimimos un .zip en memoria y recorremos contenedores anidados
def _extract_zip(content: bytes, container_name: str, nivel: int = 0,
                 extraido_total: Optional[List[int]] = None,
                 warnings: Optional[List[str]] = None) -> List[ExtractedFile]:
    # Acumulamos lo que vayamos extrayendo
    extracted: List[ExtractedFile] = []

    # Lo descomprimido hasta ahora, compartido con los niveles anidados: si no,
    # cada zak interior empezaria a contar de cero y el limite no serviria
    if extraido_total is None:
        extraido_total = [0, 0]
    elif len(extraido_total) == 1:
        extraido_total.append(0)
    if warnings is None:
        warnings = []

    # Abrimos el zip desde memoria; si está corrupto avisamos y devolvemos vacío
    try:
        # Usamos un buffer en memoria para no tocar disco
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            # Recorremos cada entrada del contenedor
            for info in archive.infolist():
                # Saltamos los directorios
                if info.is_dir():
                    continue

                extraido_total[1] += 1
                if extraido_total[1] > MAX_ENTRADAS_COMPRIMIDAS:
                    warnings.append(
                        f"Se detuvo la extracción al alcanzar "
                        f"{MAX_ENTRADAS_COMPRIMIDAS} archivos internos."
                    )
                    break

                # Conservamos la ruta interna para distinguir subcarpetas.
                name = _normalizar_ruta(info.filename)

                # Descartamos temporales y extensiones no aceptadas
                if not _should_keep(name):
                    continue

                # Antes de leer, miramos cuanto dice que ocupa descomprimido.
                #
                # `archive.read()` reserva de golpe el tamaño descomprimido, y no
                # habia limite ninguno: un zip de 42 KB cuidadosamente construido
                # se expande a gigabytes y tumba el proceso. Es la bomba de
                # descompresion clasica. Se descarta la entrada que se pase por si
                # sola, y se corta el contenedor entero al superar el total.
                if info.file_size > MAX_ENTRADA_BYTES:
                    logger.warning(
                        f"Entrada descartada por tamaño ({info.file_size} bytes) "
                        f"en {container_name}: {name}")
                    continue

                if extraido_total[0] + info.file_size > MAX_EXTRAIDO_BYTES:
                    logger.warning(
                        f"Se deja de extraer {container_name}: se alcanzo el "
                        f"limite de {MAX_EXTRAIDO_BYTES} bytes descomprimidos")
                    break

                # Leemos el contenido de la entrada
                data = archive.read(info)

                # La cifra declarada podria mentir: se cuenta lo leido de verdad
                extraido_total[0] += len(data)

                # Si la entrada es otro ZIP o RAR, descendemos hasta el límite.
                ext = get_extension(name)
                if ext in (".zip", ".rar"):
                    origen = f"{container_name} > {name}"
                    if nivel + 1 >= MAX_NIVELES_COMPRIMIDOS:
                        warnings.append(
                            f"Se omitió «{origen}» porque supera el máximo de "
                            f"{MAX_NIVELES_COMPRIMIDOS} niveles de compresión."
                        )
                    elif ext == ".zip":
                        extracted.extend(_extract_zip(
                            data, origen, nivel + 1, extraido_total, warnings
                        ))
                    else:
                        nested, error = _extract_rar(
                            data, origen, nivel + 1, extraido_total, warnings
                        )
                        extracted.extend(nested)
                        if error:
                            warnings.append(error)
                    continue

                # Guardamos el archivo con su contenedor de origen
                extracted.append(ExtractedFile(name=name, content=data, origin=container_name))

    # Un zip ilegible no debe tumbar el análisis completo
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        # Registramos el problema para poder diagnosticarlo
        logger.warning(f"Archivo comprimido ilegible, se omite: {container_name}")
        warnings.append(f"No se pudo abrir «{container_name}»: {exc}")

    # Devolvemos lo que se haya podido rescatar
    return extracted


# Descomprimimos un .rar en memoria
def _extract_rar(content: bytes, container_name: str,
                 nivel: int = 0,
                 extraido_total: Optional[List[int]] = None,
                 warnings: Optional[List[str]] = None) -> Tuple[List[ExtractedFile], Optional[str]]:
    # Importamos rarfile aquí para que la app arranque aunque no esté instalado
    try:
        # rarfile necesita el binario `unrar` disponible en el sistema
        import rarfile
    # Sin la librería no podemos abrir el contenedor
    except ImportError:
        # Devolvemos el motivo para mostrarlo en la interfaz
        return [], "El soporte de .rar no está instalado en el servidor"

    _configurar_backend_rar(rarfile)

    # Acumulamos lo extraído
    extracted: List[ExtractedFile] = []

    # El presupuesto de descompresion, compartido con el resto de la expansion
    if extraido_total is None:
        extraido_total = [0, 0]
    elif len(extraido_total) == 1:
        extraido_total.append(0)
    if warnings is None:
        warnings = []

    # Intentamos abrir el contenedor
    try:
        # Abrimos el rar desde memoria
        with rarfile.RarFile(io.BytesIO(content)) as archive:
            # Recorremos cada entrada
            for info in archive.infolist():
                # Saltamos directorios
                if info.is_dir():
                    continue

                extraido_total[1] += 1
                if extraido_total[1] > MAX_ENTRADAS_COMPRIMIDAS:
                    warnings.append(
                        f"Se detuvo la extracción al alcanzar "
                        f"{MAX_ENTRADAS_COMPRIMIDAS} archivos internos."
                    )
                    break

                # Conservamos la ruta interna para distinguir subcarpetas.
                name = _normalizar_ruta(info.filename)

                # Descartamos temporales y extensiones no aceptadas
                if not _should_keep(name):
                    continue

                # Los mismos limites que en el zip: un .rar tambien puede ser
                # una bomba de descompresion, y `archive.read()` reserva de
                # golpe el tamaño descomprimido. Sin esto la proteccion quedaba
                # a medias, tapando una via y dejando la otra abierta.
                if info.file_size > MAX_ENTRADA_BYTES:
                    logger.warning(
                        f"Entrada descartada por tamaño ({info.file_size} bytes) "
                        f"en {container_name}: {name}")
                    continue

                if extraido_total[0] + info.file_size > MAX_EXTRAIDO_BYTES:
                    logger.warning(
                        f"Se deja de extraer {container_name}: se alcanzo el "
                        f"limite de {MAX_EXTRAIDO_BYTES} bytes descomprimidos")
                    break

                # Leemos la entrada, ya comprobada
                data = archive.read(info)

                # La cifra declarada podria mentir: se cuenta lo leido de verdad
                extraido_total[0] += len(data)

                # Un RAR también puede contener ZIP/RAR a cualquier profundidad.
                ext = get_extension(name)
                if ext in (".zip", ".rar"):
                    origen = f"{container_name} > {name}"
                    if nivel + 1 >= MAX_NIVELES_COMPRIMIDOS:
                        warnings.append(
                            f"Se omitió «{origen}» porque supera el máximo de "
                            f"{MAX_NIVELES_COMPRIMIDOS} niveles de compresión."
                        )
                    elif ext == ".zip":
                        extracted.extend(_extract_zip(
                            data, origen, nivel + 1, extraido_total, warnings
                        ))
                    else:
                        nested, error = _extract_rar(
                            data, origen, nivel + 1, extraido_total, warnings
                        )
                        extracted.extend(nested)
                        if error:
                            warnings.append(error)
                    continue

                # Guardamos el archivo con su contenedor de origen
                extracted.append(ExtractedFile(name=name, content=data, origin=container_name))

    # rarfile lanza distintos errores según falte el binario o el archivo esté roto
    except Exception as exc:
        # Devolvemos el motivo para que la interfaz lo muestre en vez de fallar en silencio
        return [], f"No se pudo abrir {container_name}: {exc}"

    # Devolvemos lo extraído sin error
    return extracted, None


# Parseamos un archivo .eml y devolvemos sus datos y adjuntos
def parse_eml(content: bytes, filename: str = "correo.eml") -> EmailData:
    # Parseamos con la política moderna, que decodifica cabeceras MIME solas
    message: EmailMessage = email.message_from_bytes(content, policy=policy.default)

    # Extraemos el cuerpo en texto plano, cayendo a la versión HTML si no hay
    body = ""

    # Intentamos primero la parte de texto plano
    try:
        # get_body elige la mejor parte disponible según preferencia
        part = message.get_body(preferencelist=("plain", "html"))

        # Si encontramos una parte utilizable, la decodificamos
        if part is not None:
            # Obtenemos el contenido ya decodificado
            body = part.get_content()

            # Si vino en HTML, quitamos las etiquetas de forma básica
            if part.get_content_type() == "text/html":
                # Importamos aquí porque solo hace falta en este caso
                import re

                # Sustituimos las etiquetas por espacios para conservar la separación
                body = re.sub(r"<[^>]+>", " ", body)

                # Colapsamos los espacios repetidos
                body = re.sub(r"\s{2,}", " ", body).strip()

    # Un cuerpo ilegible no debe impedir procesar los adjuntos
    except Exception as exc:
        # Registramos el problema y seguimos con cuerpo vacío
        logger.warning(f"No se pudo leer el cuerpo de {filename}: {exc}")

    # Recolectamos los adjuntos aceptados
    attachments: List[ExtractedFile] = []

    # Recorremos las partes marcadas como adjunto
    for part in message.iter_attachments():
        # Obtenemos el nombre declarado, con uno de reserva
        name = part.get_filename() or "adjunto"

        # Descartamos temporales y extensiones no aceptadas
        if not _should_keep(name):
            continue

        # Leemos el contenido binario del adjunto
        payload = part.get_payload(decode=True)

        # Un adjunto vacío no aporta nada
        if not payload:
            continue

        # Guardamos el adjunto indicando de qué correo salió
        attachments.append(ExtractedFile(name=name, content=payload, origin=filename))

    # Devolvemos los datos del correo ya normalizados
    return EmailData(
        sender=str(message.get("From", "N/A")),
        to=str(message.get("To", "N/A")),
        subject=str(message.get("Subject", "Sin asunto")),
        date=str(message.get("Date", "N/A")),
        body=body or "Sin contenido",
        attachments=attachments,
    )


# Procesamos los archivos que subió el usuario y devolvemos la lista final
def process_uploads(uploads: List[Tuple[str, bytes]]) -> Dict[str, object]:
    """Expande contenedores y correos, y devuelve los archivos listos para analizar.

    Recibe pares (nombre, contenido) tal como llegan del formulario. Devuelve un
    diccionario con los archivos finales, los datos del primer correo encontrado
    y los avisos que haya que mostrar al usuario.
    """
    # Acumulamos los archivos que se van a analizar
    files: List[ExtractedFile] = []

    # Lo descomprimido en TODA esta expansion, compartido por todos los
    # contenedores. Darle un presupuesto propio a cada uno no servia de nada:
    # dentro del limite de subida caben muchos comprimidos pequeños, y cada uno
    # se habria podido expandir hasta el tope por su cuenta.
    extraido_total = [0, 0]

    # Acumulamos los avisos para mostrarlos en la interfaz
    warnings: List[str] = []

    # Guardamos los datos del primer correo, que son los del asunto y remitente
    email_data: Optional[EmailData] = None

    # Recorremos cada archivo subido
    for name, content in uploads:
        # Obtenemos la extensión para decidir cómo tratarlo
        ext = get_extension(name)

        # El selector de carpetas también entrega temporales de Office y
        # archivos ocultos; se descartan aunque lleguen fuera de un comprimido.
        if is_temp_file(name):
            continue

        # Los correos aportan datos de cabecera y sus propios adjuntos
        if ext == ".eml":
            # Parseamos el correo
            parsed = parse_eml(content, name)

            # Conservamos los datos del primero: son los que encabezan el informe
            if email_data is None:
                email_data = parsed

            # Sumamos sus adjuntos a la lista de análisis
            for attachment in parsed.attachments:
                adjunto_ext = get_extension(attachment.name)
                if adjunto_ext == ".zip":
                    files.extend(_extract_zip(
                        attachment.content,
                        f"{name} > {attachment.name}",
                        extraido_total=extraido_total,
                        warnings=warnings,
                    ))
                elif adjunto_ext == ".rar":
                    extraidos, error = _extract_rar(
                        attachment.content,
                        f"{name} > {attachment.name}",
                        extraido_total=extraido_total,
                        warnings=warnings,
                    )
                    files.extend(extraidos)
                    if error:
                        warnings.append(error)
                else:
                    files.append(attachment)

            # Avisamos si el correo no traía nada analizable
            if not parsed.attachments:
                warnings.append(f"El correo «{name}» no contiene adjuntos analizables.")

            # Seguimos con el próximo archivo subido
            continue

        # Los .zip se expanden en memoria
        if ext == ".zip":
            # Extraemos su contenido
            extracted = _extract_zip(content, name,
                                     extraido_total=extraido_total,
                                     warnings=warnings)

            # Sumamos lo extraído
            files.extend(extracted)

            # Avisamos si el contenedor no aportó nada
            if not extracted:
                warnings.append(f"El comprimido «{name}» no contiene archivos analizables.")

            # Seguimos con el próximo archivo subido
            continue

        # Los .rar necesitan el binario unrar en el servidor
        if ext == ".rar":
            # Intentamos extraer
            extracted, error = _extract_rar(content, name,
                                            extraido_total=extraido_total,
                                            warnings=warnings)

            # Si falló, dejamos constancia visible en vez de perder el archivo en silencio
            if error:
                warnings.append(error)

            # Sumamos lo que se haya podido extraer
            files.extend(extracted)

            # Seguimos con el próximo archivo subido
            continue

        # El formato 7z nunca estuvo soportado de verdad: la versión React lo
        # aceptaba en el input pero fallaba al abrirlo y lo descartaba en silencio.
        if ext in (".7z", ".7zip"):
            # Ahora lo decimos explícitamente
            warnings.append(f"El formato 7z no está soportado; «{name}» se omitió.")

            # Seguimos con el próximo archivo subido
            continue

        # Cualquier otro archivo aceptado entra tal cual
        if ext in ACCEPTED_EXTENSIONS:
            # Lo agregamos sin contenedor de origen
            files.append(ExtractedFile(name=name, content=content, origin=""))

        # Un formato desconocido se descarta con aviso
        else:
            # Dejamos constancia para el usuario
            warnings.append(f"«{name}» tiene un formato no soportado y se omitió.")

    # Descartamos duplicados por nombre y contenido, que aparecen cuando el mismo
    # documento viene suelto y además dentro del comprimido.
    unique: List[ExtractedFile] = []

    # Guardamos las firmas ya vistas
    seen: set = set()

    # Recorremos en orden para conservar la primera aparición
    for item in files:
        # Firmamos por nombre y tamaño, que basta para este caso
        signature = (item.name.lower(), item.size)

        # Saltamos si ya lo teníamos
        if signature in seen:
            continue

        # Registramos la firma y conservamos el archivo
        seen.add(signature)
        unique.append(item)

    # Devolvemos todo lo que necesita el paso de análisis
    return {
        "files": unique,
        "email": email_data or EmailData(),
        "warnings": warnings,
    }
