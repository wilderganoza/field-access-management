"""Punto de entrada de la aplicación FastAPI.

La app se sirve entera desde este proceso: Jinja2 renderiza el HTML y HTMX pide
fragmentos a los mismos endpoints. No hay build de frontend ni API JSON separada.
"""

# Importamos las librerias necesarias
from contextlib import asynccontextmanager  # Para el ciclo de vida de la app

from fastapi import FastAPI, Request  # App y request
from fastapi.responses import RedirectResponse  # Para el alias de usuarios
from fastapi.staticfiles import StaticFiles  # Para servir css/js
from starlette.middleware.cors import CORSMiddleware  # CORS, si algo externo lo necesita

from app.core.config import settings  # Configuración global
from app.core.deps import RedirectToLogin, login_redirect  # Sesión
from app.core.logging import get_logger  # Logging
from app.db.session import db_manager  # Conexión a PostgreSQL
from app.web import auth as auth_routes  # Rutas de autenticación
from app.web import cases as cases_routes  # Gestión de casos y checklist
from app.web import history as history_routes  # Historial de solicitudes
from app.web import prompts as prompts_routes  # Edición de la plantilla de análisis
from app.web import requests as request_routes  # Flujo de carga y análisis
from app.web import roles as roles_routes  # Perfiles y permisos por módulo
from app.web import settings as settings_routes  # Configuración del proveedor de IA
from app.web import users as users_routes  # Administración de cuentas
from app.web.templating import STATIC_DIR  # Plantillas y estáticos

# Creamos el logger de este módulo
logger = get_logger(__name__)


# Definimos el ciclo de vida: abrimos la base al arrancar y la cerramos al salir
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Registramos el arranque
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.ENVIRONMENT}]")

    # Abrimos el pool de conexiones
    db_manager.initialize()

    # Y montamos el cliente HTTP ahora, no en la primera llamada.
    #
    # Crear el contexto TLS cuesta ~38 s en este entorno (Windows enumera su
    # almacen de certificados). Pagarlo aqui, mientras arranca, evita que se lo
    # coma el primer usuario que suba un documento o lance un analisis.
    from app.core import http

    http.cliente()

    # Cedemos el control mientras la app atiende requests
    yield

    # Cerramos el pool al apagar
    db_manager.dispose()

    # Y el cliente HTTP compartido
    http.cerrar()


# Construimos la aplicación
# La documentacion interactiva solo se publica fuera de produccion. Abierta,
# `/docs` y `/openapi.json` enumeran a cualquiera que pase —sin sesion— todas
# las rutas de la aplicacion con sus parametros.
_DOCS = {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}

if settings.ENVIRONMENT == "production" and not settings.DEBUG:
    _DOCS = {"docs_url": None, "redoc_url": None, "openapi_url": None}

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
    **_DOCS,
)

# Habilitamos CORS solo si hay orígenes configurados explícitamente
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# El orden de los middlewares importa, y va al reves de como se leen: Starlette
# pone el ULTIMO registrado por FUERA. Escritos asi, se ejecutan
#
#     sin_cache -> renovar_sesion -> la ruta
#
# Renovamos la sesión sola mientras haya actividad.
#
# El token dura ocho horas. Sin esto, a las ocho horas justas la siguiente
# pantalla manda al login aunque el usuario lleve toda la tarde trabajando. Al
# pasar de la mitad de su vida se emite uno nuevo, así que una jornada continua
# nunca corta; una sesión abandonada, en cambio, sí caduca.
#
# Antes esto pedía un token nuevo a Supabase Auth con la cookie de refresco. Ya
# no hay refresco ni Supabase Auth: el token lo firmamos nosotros y renovarlo
# es volver a firmarlo.
@app.middleware("http")
async def renovar_sesion(request: Request, call_next):
    from app.core.security import create_access_token, decode_claims, id_de_usuario
    from app.web.auth import _set_session_cookie

    # Los estáticos y el propio login no necesitan sesión
    if request.url.path.startswith(("/static", "/login", "/logout")):
        return await call_next(request)

    token = request.cookies.get(settings.SESSION_COOKIE_NAME, "")

    if not token:
        return await call_next(request)

    claims = decode_claims(token)

    # Un token que no vale ya no se renueva: se deja que la ruta redirija al
    # login, que es lo correcto cuando la sesión terminó de verdad
    if not claims:
        return await call_next(request)

    emitido = claims.get("iat")
    caduca = claims.get("exp")

    # Sin las dos marcas no se puede saber si va por la mitad
    if not emitido or not caduca:
        return await call_next(request)

    import time as _time

    mitad = emitido + (caduca - emitido) / 2

    # Todavía no llega a la mitad: no hay nada que renovar
    if _time.time() < mitad:
        return await call_next(request)

    user_id = id_de_usuario(claims)

    if user_id is None:
        return await call_next(request)

    response = await call_next(request)

    # Se repone la cookie con un token recién firmado. No hace falta tocar el
    # request: los claims que ya se leyeron siguen siendo válidos.
    _set_session_cookie(response, create_access_token(user_id))

    return response


# Las pantallas no se guardan en la cache del navegador.
#
# Los fragmentos que pide HTMX van siempre a la misma direccion —«/cases»—
# asi que el navegador los reutilizaba y seguia enseñando la tabla anterior
# despues de cambiar el servidor. Los estaticos si se cachean: llevan la marca
# de tiempo del archivo en la URL.
@app.middleware("http")
async def sin_cache(request: Request, call_next):
    response = await call_next(request)

    if not request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-store, must-revalidate"

    return response


# Montamos los archivos estáticos
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Registramos las rutas de autenticación
app.include_router(auth_routes.router, tags=["auth"])

# Registramos el flujo principal: nueva solicitud, análisis y resultados
app.include_router(request_routes.router, tags=["solicitudes"])

# Registramos el historial de solicitudes procesadas
app.include_router(history_routes.router, tags=["historial"])

# Registramos la gestión de casos de validación
app.include_router(cases_routes.router, tags=["casos"])

# Registramos la edición de la plantilla de análisis
app.include_router(prompts_routes.router, tags=["prompts"])

# Configuración global del proveedor de inteligencia artificial
app.include_router(settings_routes.router, tags=["configuración"])

# Registramos la administración de cuentas, restringida a administradores
app.include_router(users_routes.router, tags=["usuarios"])

# Los perfiles: que puede hacer cada uno en cada modulo
app.include_router(roles_routes.router, tags=["roles"])


# Convertimos la excepción de sesión ausente en una redirección al login.
# Sin esto, HTMX recibiría un 307 sin cuerpo y la pantalla quedaría congelada.
@app.exception_handler(RedirectToLogin)
async def handle_redirect_to_login(request: Request, exc: RedirectToLogin):
    # Armamos la redirección conservando el destino original
    response = login_redirect(exc.next_url)

    # Si la petición vino de HTMX, le pedimos que redirija la ventana completa
    if request.headers.get("HX-Request") == "true":
        response.headers["HX-Redirect"] = response.headers.get("location", "/login")

    # Devolvemos la redirección
    return response


# El menu enlaza `/admin/users`, que es como se llama en la aplicacion hermana.
# El router vive en `/users`; esto redirige para que las dos direcciones valgan.
@app.get("/admin/users")
def alias_usuarios():
    return RedirectResponse("/users", status_code=307)


# Exponemos un chequeo de salud para el balanceador y los despliegues
@app.get("/health")
def health():
    # Devolvemos el estado y la versión
    return {"status": "ok", "version": settings.APP_VERSION}
