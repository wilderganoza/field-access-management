# Importamos las librerias necesarias
import logging  # Librería estándar de logging
import sys  # Para escribir los logs a stdout

from app.core.config import settings  # Para leer el nivel de log configurado

# Guardamos una bandera para configurar el logging una sola vez por proceso
_CONFIGURED = False


# Configuramos el logging raíz la primera vez que alguien pide un logger
def _configure() -> None:
    # Usamos la bandera de módulo para no reconfigurar en cada llamada
    global _CONFIGURED

    # Si ya configuramos, no repetimos el trabajo
    if _CONFIGURED:
        return

    # La salida se fuerza a UTF-8, y lo que no quepa se sustituye.
    #
    # Sin esto una linea de registro puede TUMBAR LA PETICION: en Windows la
    # consola arranca con una pagina de codigos que no representa un emoji, y
    # los datos del usuario acaban en el registro —el icono de un caso, un
    # nombre con tilde—. Al escribirlos, `logging` lanzaba UnicodeEncodeError
    # dentro del manejador de errores, y una peticion que iba a devolver un
    # mensaje legible terminaba en un 500.
    #
    # `errors="replace"` es deliberado: perder un caracter en el registro es
    # aceptable, perder la peticion no.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    # En un stdout que no admite reconfigurarse (algunos entornos lo
    # reemplazan) se sigue: el manejador de abajo tiene su propia red
    except (AttributeError, ValueError):
        pass

    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    ))

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        handlers=[manejador],
        force=True,
    )

    # Marcamos que ya quedó configurado
    _CONFIGURED = True


# Devolvemos un logger listo para usar en cualquier módulo
def get_logger(name: str) -> logging.Logger:
    # Nos aseguramos de que el logging raíz esté configurado
    _configure()

    # Devolvemos el logger con el nombre del módulo que lo pidió
    return logging.getLogger(name)
