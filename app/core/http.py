"""Cliente HTTP compartido para las llamadas salientes.

Existe por un motivo medido. En esta máquina, montar el contexto TLS tarda
**38 segundos**:

    leer cacert.pem      0.03s
    crear contexto SSL  38.07s   <-- aquí
    crear httpx.Client  39.88s
    peticion 1           0.66s
    peticion 2           0.42s

La red no tiene nada que ver: por socket crudo, DNS + TCP + TLS + petición suman
menos de un segundo. Lo que cuesta es `ssl.create_default_context()`, que en
Windows enumera además el almacén de certificados del sistema.

Con un cliente nuevo por llamada —que es como estaba— cada archivo subido
pagaba esos 38 segundos. Aquí el cliente se crea UNA vez y se reutiliza: la
primera llamada del proceso los paga, y las siguientes tardan medio segundo.

`httpx.Client` admite ser usado desde varios hilos, que es justo lo que hace
FastAPI al correr las rutas síncronas en el threadpool. Por eso se comparte en
vez de guardarlo por hilo.
"""

# Importamos las librerias necesarias
import threading  # Para crear el cliente una sola vez aunque lleguen dos a la vez
from typing import Optional  # Para el plazo opcional

import httpx  # Cliente HTTP

# El plazo por defecto de una llamada saliente, en segundos
PLAZO_POR_DEFECTO = 60.0

# El cliente compartido y el cerrojo que protege su creación
_cliente: Optional[httpx.Client] = None
_cliente_async: Optional[httpx.AsyncClient] = None
_cerrojo = threading.Lock()


# Devolvemos el cliente compartido, creándolo la primera vez
def cliente(timeout: Optional[float] = None) -> httpx.Client:
    """El cliente HTTP del proceso.

    NO se debe cerrar ni usar con `with`: es compartido, y cerrarlo dejaría al
    resto de la aplicación sin él. El plazo se pasa por llamada.
    """
    global _cliente

    if _cliente is None:
        # Dos hilos pueden llegar juntos en el arranque; solo uno lo crea
        with _cerrojo:
            if _cliente is None:
                _cliente = httpx.Client(timeout=PLAZO_POR_DEFECTO)

    return _cliente


# Y el plazo, cuando una llamada concreta necesita otro
def plazo(segundos: Optional[float]) -> httpx.Timeout:
    """El plazo para una llamada suelta, sin tocar el del cliente."""
    return httpx.Timeout(segundos if segundos is not None else PLAZO_POR_DEFECTO)


# La versión asíncrona, para las rutas que sí son async de verdad
def cliente_async(timeout: Optional[float] = None) -> httpx.AsyncClient:
    """El cliente asíncrono del proceso. Tampoco se cierra."""
    global _cliente_async

    if _cliente_async is None:
        with _cerrojo:
            if _cliente_async is None:
                _cliente_async = httpx.AsyncClient(timeout=PLAZO_POR_DEFECTO)

    return _cliente_async


# Cerramos los clientes al apagar la aplicación
def cerrar() -> None:
    """Suelta las conexiones abiertas. Se llama desde el `lifespan`."""
    global _cliente, _cliente_async

    if _cliente is not None:
        _cliente.close()
        _cliente = None

    # El asincrono se cierra desde una corutina; aqui solo se suelta la
    # referencia, y el proceso al terminar libera el socket
    _cliente_async = None
