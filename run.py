"""Arranque del servidor de desarrollo.

En producción se lanza uvicorn directamente contra app.main:app.
"""

# Importamos las librerias necesarias
import uvicorn  # Servidor ASGI

from app.core.config import settings  # Host, puerto y modo debug


# Arrancamos el servidor cuando el archivo se ejecuta directamente
if __name__ == "__main__":
    # Levantamos uvicorn con recarga automática solo en modo debug
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
