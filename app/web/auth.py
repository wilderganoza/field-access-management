"""Rutas de autenticación: login, logout y cambio de contraseña.

La aplicación es ahora su propio servidor de identidad: la contraseña se
comprueba contra `users.password_hash` y el token lo firmamos nosotros. Antes
esto hablaba con Supabase Auth (GoTrue) y aquí solo quedaba un perfil.

Sesión de un solo token, sin pareja de refresco: dura ocho horas y se renueva
sola al pasar de la mitad de su vida, mientras haya actividad. Un token de
refresco aparte sirve cuando el cliente es un navegador que guarda la sesión
durante semanas; aquí la sesión es de jornada.
"""

# Importamos las librerias necesarias
import time  # Para fechar los intentos fallidos
from collections import defaultdict  # Para el contador por origen
from datetime import datetime, timezone  # Para anotar la última entrada
from typing import Dict, List  # Tipos del contador

from fastapi import APIRouter, Depends, Form, Request, Response  # Router y formularios
from fastapi.responses import HTMLResponse, RedirectResponse  # Respuestas
from sqlalchemy import func  # Para comparar sin distinguir mayúsculas
from sqlalchemy.orm import Session  # Sesión de base de datos

from app.core.config import settings  # Nombres de cookies y flags
from app.core.deps import get_current_user, get_current_user_optional  # Sesión
from app.core.logging import get_logger  # Para registrar los bloqueos
from app.core.security import (  # Contraseñas y token propio
    create_access_token, hash_password, needs_rehash, quemar_tiempo, verify_password,
)
from app.db.session import get_db  # Dependencia de sesión
from app.models.analysis import User  # La cuenta
from app.web.templating import page_context, templates  # Plantillas

# Creamos el logger de este módulo
logger = get_logger(__name__)

# Creamos el router de autenticación
router = APIRouter()

# El mismo mínimo que exige la pantalla de usuarios
MIN_PASSWORD = 8


# Nos quedamos solo con los destinos internos de `next`.
#
# `next` llega del query string y del formulario, y se usaba tal cual en la
# redirección posterior al login. Un enlace a
# `/login?next=https://sitio-falso.example` mandaba al usuario fuera del sitio
# después de autenticarse —y, si ya tenía sesión, de inmediato—, que es la forma
# habitual de dar apariencia legítima a una página de phishing.
def destino_seguro(next_url: str) -> str:
    """La ruta pedida si es interna, y la raíz si no lo es."""
    # Vacío o ausente significa la raíz
    if not next_url:
        return "/"

    candidato = next_url.strip()

    # Tiene que ser una ruta absoluta de este sitio: empieza por una sola barra.
    # `//otro-sitio` es una URL relativa al protocolo y saldría fuera; una barra
    # invertida la normalizan algunos navegadores a `//`, así que tampoco pasa.
    if not candidato.startswith("/") or candidato.startswith(("//", "/\\")):
        return "/"

    # Y no puede traer esquema ni credenciales por delante
    if ":" in candidato.split("/")[0]:
        return "/"

    # Devolvemos el destino, que ya es interno
    return candidato


# Freno a la fuerza bruta sobre el login.
#
# Se cuentan solo los intentos FALLIDOS, por IP y correo, y entrar bien limpia el
# contador, así que quien sabe su contraseña nunca lo nota.
#
# Vive en memoria del proceso: con varios workers cada uno lleva su cuenta, de
# modo que el límite efectivo se multiplica por el número de workers. Es un
# freno, no una garantía.
INTENTOS_MAX = 10
VENTANA_INTENTOS = 300  # segundos

# Intentos fallidos recientes, por clave (IP + correo)
_fallos: Dict[str, List[float]] = defaultdict(list)


# Componemos la clave con la que se cuentan los intentos
def _clave_intentos(request: Request, email: str) -> str:
    """Identifica el par (quién llama, a qué cuenta)."""
    # `client.host` puede no estar tras algunos proxies; entonces se cuenta solo
    # por correo, que sigue protegiendo la cuenta concreta
    ip = getattr(request.client, "host", "") or "sin-ip"

    return f"{ip}|{email.strip().lower()}"


# Decimos si ese origen ya agotó sus intentos
def _demasiados_intentos(clave: str) -> bool:
    """True si hay que rechazar sin llegar a comprobar la contraseña."""
    ahora = time.monotonic()

    # Nos quedamos solo con los de la ventana vigente
    recientes = [t for t in _fallos[clave] if ahora - t < VENTANA_INTENTOS]
    _fallos[clave] = recientes

    return len(recientes) >= INTENTOS_MAX


# Anotamos un intento fallido
def _anotar_fallo(clave: str) -> None:
    _fallos[clave].append(time.monotonic())


# Y limpiamos el contador cuando la entrada es correcta
def _limpiar_intentos(clave: str) -> None:
    _fallos.pop(clave, None)


# Guardamos el token de sesión en una cookie httpOnly
def _set_session_cookie(response: Response, token: str) -> None:
    """El navegador la envía sola; JavaScript no puede leerla."""
    response.set_cookie(
        settings.SESSION_COOKIE_NAME,
        token,
        max_age=settings.SESSION_TTL_MINUTES * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        # `lax` deja pasar la navegación normal y corta el envío en peticiones
        # cruzadas, que es lo que evita el CSRF en los formularios
        samesite="lax",
        path="/",
    )


# Borramos la cookie de sesión
def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")


# Mostramos el formulario de login
@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str = "/"):
    # Si ya hay sesión activa, no tiene sentido mostrar el formulario
    if get_current_user_optional(request) is not None:
        # Mandamos directo al destino pedido, si es interno
        return RedirectResponse(destino_seguro(next), status_code=303)

    # Renderizamos la pantalla de login
    return templates.TemplateResponse(
        "pages/login.html",
        page_context(request, current_user=None, next_url=next, error=None),
    )


# Procesamos el envío del formulario de login
@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    # El mismo mensaje para cualquier fallo: decir «ese correo no existe»
    # convierte el login en un buscador de cuentas
    GENERICO = "Usuario o contraseña incorrectos"

    def rechazar(mensaje: str = GENERICO, codigo: int = 401):
        return templates.TemplateResponse(
            "pages/login.html",
            page_context(request, current_user=None, next_url=next, error=mensaje),
            status_code=codigo,
        )

    # Antes de comprobar nada, miramos si este origen ya agotó sus intentos
    clave_intentos = _clave_intentos(request, email)

    if _demasiados_intentos(clave_intentos):
        logger.warning(f"Login bloqueado por demasiados intentos: {clave_intentos}")

        return rechazar(
            "Demasiados intentos fallidos. Espera unos minutos y vuelve a probar.", 429)

    # Buscamos la cuenta por correo, sin distinguir mayúsculas
    correo = (email or "").strip()

    fila = (db.query(User)
            .filter(func.lower(User.email) == correo.lower())
            .first())

    # Una cuenta que no existe se responde igual que una contraseña mala, y
    # tardando lo mismo: sin esto la diferencia de tiempo delata qué correos
    # están dados de alta
    if fila is None:
        quemar_tiempo()
        _anotar_fallo(clave_intentos)

        return rechazar()

    # La contraseña
    if not verify_password(password, fila.password_hash):
        _anotar_fallo(clave_intentos)
        logger.info(f"Contraseña incorrecta para {correo}")

        return rechazar()

    # Una cuenta dada de baja no entra, y se le dice: aquí ya demostró ser quien
    # dice, así que el mensaje concreto no filtra nada que no supiera
    if not fila.is_active:
        logger.warning(f"Entrada rechazada: la cuenta {correo} está desactivada")

        return rechazar("Esta cuenta está desactivada. Habla con un administrador.", 403)

    # Entró bien: el contador de esa cuenta se limpia
    _limpiar_intentos(clave_intentos)

    # Si los parámetros de argon2 se endurecieron desde la última vez, se
    # rehashea ahora, con la contraseña que acaba de escribir y sin pedirle nada
    if needs_rehash(fila.password_hash):
        fila.password_hash = hash_password(password)

    fila.last_login_at = datetime.now(timezone.utc)

    # Anotar la entrada y el posible rehash es util, pero NO es motivo para no
    # dejar entrar: la contrasena ya se comprobo. Si la escritura falla se sigue
    # con la sesion y se deja rastro.
    try:
        db.commit()

    except Exception as exc:
        db.rollback()
        logger.warning(f"No se pudo anotar la entrada de {correo}: {exc}")

    logger.info(f"Entrada correcta: {correo}")

    # Redirigimos al destino original con la cookie ya puesta
    response = RedirectResponse(destino_seguro(next), status_code=303)

    _set_session_cookie(response, create_access_token(fila.id))

    return response


# Cerramos la sesión
@router.post("/logout")
def logout(request: Request):
    # Mandamos al login
    response = RedirectResponse("/login", status_code=303)

    # Y borramos la cookie. Al ser un token firmado y sin estado, esto es lo
    # que termina la sesión en el navegador; el token seguiría siendo válido
    # hasta que venza si alguien lo hubiera copiado antes, que es el precio de
    # no guardar sesiones en la base.
    _clear_session_cookie(response)

    return response


# El cambio de contraseña obligatorio: a una cuenta recién creada -o recién
# reseteada- por un administrador se le pide poner una que solo el dueño
# conozca antes de dejarla entrar a cualquier otro sitio.
@router.get("/change-password", response_class=HTMLResponse)
def change_password_form(request: Request, next: str = "/",
                         current_user: dict = Depends(get_current_user)):
    return templates.TemplateResponse(
        "pages/change_password.html",
        page_context(request, current_user=current_user, next_url=next,
                     error=None, min_password=MIN_PASSWORD),
    )


@router.post("/change-password", response_class=HTMLResponse)
def change_password_submit(
    request: Request,
    password: str = Form(...),
    password_confirm: str = Form(...),
    next: str = Form("/"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    def error(mensaje: str):
        return templates.TemplateResponse(
            "pages/change_password.html",
            page_context(request, current_user=current_user, next_url=next,
                         error=mensaje, min_password=MIN_PASSWORD),
            status_code=400,
        )

    if len(password) < MIN_PASSWORD:
        return error(f"La contraseña debe tener al menos {MIN_PASSWORD} caracteres.")

    if password != password_confirm:
        return error("Las contraseñas no coinciden.")

    fila = db.query(User).filter(User.id == current_user["id"]).first()

    if fila is None:
        return error("La cuenta ya no existe.")

    # Ya puso una propia: no hace falta pedirla de nuevo
    fila.password_hash = hash_password(password)
    fila.must_change_password = False

    # Aqui si importa saber si se guardo: decirle que su contrasena cambio
    # cuando no cambio lo deja fuera en la siguiente entrada
    try:
        db.commit()

    except Exception as exc:
        db.rollback()
        logger.warning(f"No se pudo cambiar la contraseña de {current_user['email']}: {exc}")

        return error("No se pudo guardar la contraseña nueva. Inténtalo de nuevo.")

    logger.info(f"{current_user['email']} cambió su contraseña")

    # El token no cambia -sigue siendo la misma sesión-, pero se repone la
    # cookie para que el usuario no quede a media vida del token tras el cambio
    response = RedirectResponse(destino_seguro(next), status_code=303)

    _set_session_cookie(response, create_access_token(fila.id))

    return response
