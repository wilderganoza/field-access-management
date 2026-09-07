"""Dependencias de FastAPI para resolver el usuario de la sesión.

La identidad ya no viene de Supabase Auth: el token lo emite esta aplicación y
el usuario vive en `users`, en su propio esquema. Lo que sí se mantiene es que
la cookie es httpOnly y que el token va firmado con el secreto del proyecto,
para que PostgREST lo acepte y las políticas RLS puedan evaluarlo.

El usuario se resuelve una vez por petición y se guarda en el propio request:
antes se pedía cuatro veces por pantalla —dos desde el middleware y dos desde la
dependencia de la ruta— y cada una costaba varias consultas.
"""

# Importamos las librerias necesarias
from typing import Optional  # Para tipar el usuario que puede no existir

from fastapi import Request  # Para leer las cookies del request
from fastapi.responses import RedirectResponse  # Para mandar al login
from starlette.datastructures import FormData  # Tipo del formulario ya leído
from starlette.exceptions import HTTPException  # Para cortar el request

from app.core.config import settings  # Nombres de las cookies
from app.core.logging import get_logger  # Para dejar rastro de los fallos
from app.core.security import decode_claims, id_de_usuario  # Lectura del token

# Creamos el logger de este módulo
logger = get_logger(__name__)


# Entregamos el formulario ya leído, para que la ruta pueda ser síncrona.
#
# Leer el cuerpo de una petición es asíncrono, y era lo único que obligaba a una
# decena de rutas a declararse `async def`. Una ruta `async` con SQLAlchemy
# síncrono dentro bloquea el bucle de eventos en cada consulta: mientras dura,
# el servidor no atiende a nadie más. Con el formulario resuelto aquí, esas
# rutas pasan a `def` y FastAPI las corre en el threadpool, donde bloquear es
# lo esperado y no se lleva por delante al resto.
async def formulario_enviado(request: Request) -> FormData:
    """El formulario de la petición, ya parseado."""
    # Starlette lo cachea en la petición, así que volver a pedirlo no cuesta
    return await request.form()


# Definimos la excepción que redirige al login en vez de devolver un 401 crudo.
# Con HTMX importa: un 401 sin cuerpo deja la pantalla congelada.
class RedirectToLogin(HTTPException):
    # Construimos la excepción con el destino al que volver tras autenticarse
    def __init__(self, next_url: str = "/"):
        # Guardamos el destino para armar el querystring
        self.next_url = next_url

        # Usamos 307 para que el navegador conserve el método original
        super().__init__(status_code=307, detail="Authentication required")


# Extraemos el usuario de la cookie, sin exigir que exista.
#
# El resultado se guarda en el propio request, con el token como clave: si la
# sesión se renueva a mitad de petición, la clave cambia y se vuelve a resolver.
def get_current_user_optional(request: Request) -> Optional[dict]:
    # Leemos el token de la cookie httpOnly
    token = request.cookies.get(settings.SESSION_COOKIE_NAME, "")

    # Si ya se resolvió en esta misma petición, y con este mismo token, vale
    cacheado = getattr(request.state, "usuario_resuelto", None)

    if cacheado is not None and cacheado[0] == token:
        return cacheado[1]

    # Lo resolvemos y lo dejamos guardado para el resto de la petición
    usuario = _resolver_usuario(token)

    request.state.usuario_resuelto = (token, usuario)

    return usuario


# Resolvemos el usuario de verdad, sin cache de por medio
def _resolver_usuario(token: str) -> Optional[dict]:
    # Sin token no hay sesión
    if not token:
        return None

    # Comprobamos la firma y la vigencia. Un token que no emitimos nosotros, o
    # que ya venció, equivale a no tener sesión.
    claims = decode_claims(token)

    if not claims:
        return None

    user_id = id_de_usuario(claims)

    if user_id is None:
        return None

    # Se usa sesión propia: esto lo llama una dependencia, que no la recibe
    try:
        from app.db.session import db_manager
        from app.models.analysis import User
        from app.services import permisos as servicio_permisos

        with db_manager.session() as db:
            fila = db.query(User).filter(User.id == user_id).first()

            # Una cuenta que ya no existe, o que un administrador dio de baja,
            # no entra. La baja es una decisión explícita y tiene que surtir
            # efecto en la siguiente petición, no cuando venza el token.
            if fila is None or not fila.is_active:
                return None

            # Los permisos del perfil, resueltos de una vez con la herencia
            # padre→hijo ya aplicada
            mapa = servicio_permisos.cargar(db, fila.role_id)

            # Y con que modulo se gobierna cada tabla, que es lo que necesita
            # el guardian de las rutas del mantenedor generico
            tablas = servicio_permisos.tablas_por_modulo(db)

            # Se devuelve un diccionario, no la fila: la sesión se cierra aquí
            # y una instancia desligada estallaría al leerla desde la plantilla
            return {
                "id": fila.id,
                "email": fila.email or "",
                "username": fila.username or "",
                "full_name": fila.full_name or fila.email or "",
                "department": fila.department or "",
                "position": fila.position or "",
                "role_id": fila.role_id,
                "role_key": fila.role.key if fila.role else None,
                "role_name": fila.role.name if fila.role else "Sin perfil",
                # Se conserva `is_admin` porque lo consultan las plantillas y
                # las rutas de administración. Ahora se deduce del perfil, no
                # de una columna de texto.
                "is_admin": bool(fila.role and fila.role.key == "admin"),
                "must_change_password": bool(fila.must_change_password),
                "permisos": mapa,
                "tablas": tablas,
            }

    # Si la base no responde no se puede afirmar quién es nadie, y conceder
    # privilegios por lo que diga el token sería peor: se trata como sin sesión.
    # Se deja rastro porque un fallo aquí —una columna renombrada, un import mal
    # escrito— dejaría a todo el mundo fuera y en silencio parecería otra cosa.
    except Exception as exc:
        logger.warning(f"No se pudo resolver la sesión: {type(exc).__name__}: {exc}")
        return None


# Extraemos el usuario exigiendo que haya sesión
def get_current_user(request: Request) -> dict:
    # Reutilizamos la versión opcional
    user = get_current_user_optional(request)

    # Sin usuario, cortamos el request redirigiendo al login
    if user is None:
        # Conservamos la ruta pedida para volver a ella tras autenticarse
        raise RedirectToLogin(next_url=request.url.path)

    # Devolvemos el usuario autenticado
    return user


# Exigimos además que el usuario sea administrador
def require_admin(request: Request) -> dict:
    # Primero resolvemos que haya sesión válida
    user = get_current_user(request)

    # Sin rol admin, devolvemos 403: está autenticado, no autorizado
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Se requiere rol de administrador")

    # Devolvemos el usuario administrador
    return user


# Exigimos un permiso concreto sobre un módulo.
#
# Se usa como dependencia en las rutas: `Depends(exige('assets.wells', 'delete'))`.
# Así el permiso se comprueba en el servidor y no solo escondiendo el botón, que
# es decoración: quien conozca la URL la llama igual.
def exige(modulo: str, accion: str = "view"):
    """Devuelve una dependencia que exige ese permiso."""
    from app.services import permisos as servicio_permisos

    def comprobar(request: Request) -> dict:
        # Primero que haya sesión
        user = get_current_user(request)

        # Y luego que el perfil lo permita
        if not servicio_permisos.puede(user, modulo, accion):
            raise HTTPException(
                status_code=403,
                detail=f"Tu perfil no permite «{accion}» en este módulo.",
            )

        return user

    return comprobar


# Exigimos un permiso sobre la TABLA que maneja la ruta.
#
# El mantenedor generico sirve 47 tablas con el mismo codigo, asi que no puede
# nombrar su modulo: lo que sabe es sobre que tabla opera. `modules.table_name`
# ata las dos cosas, y es el mismo vinculo que usan las politicas RLS -- de modo
# que servidor y base autorizan por el mismo criterio y no pueden discrepar.
def exige_tabla(tabla: str, accion: str = "view"):
    """Devuelve una dependencia que exige ese permiso sobre esa tabla."""
    from app.services import permisos as servicio_permisos

    def comprobar(request: Request) -> dict:
        user = get_current_user(request)

        if not servicio_permisos.puede_tabla(user, tabla, accion):
            raise HTTPException(
                status_code=403,
                detail=f"Tu perfil no permite «{accion}» sobre este módulo.",
            )

        return user

    return comprobar


# Construimos la redirección al login conservando el destino original
def login_redirect(next_url: str = "/") -> RedirectResponse:
    # Evitamos redirigir al propio login, que causaría un bucle
    destination = "/login" if next_url in ("/login", "/logout") else f"/login?next={next_url}"

    # Devolvemos un 303 para que el navegador cambie a GET
    return RedirectResponse(destination, status_code=303)
