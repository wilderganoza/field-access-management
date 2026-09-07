# Importamos las librerias necesarias
import json  # Para serializar los claims del contexto

from fastapi import Request  # Para leer el usuario ya resuelto
from typing import Generator  # Para tipar el generador de sesiones
from sqlalchemy import create_engine, event  # Engine y enganche a la conexión
from sqlalchemy.orm import sessionmaker, Session  # Fábrica de sesiones y tipo de sesión

from app.core.config import settings  # Configuración de la app (DATABASE_URL, DB_SCHEMA)
from app.core.logging import get_logger  # Para registrar la actividad de conexión

# Creamos el logger de este módulo
logger = get_logger(__name__)


# Centralizamos la conexión a PostgreSQL: el engine y la fábrica de sesiones.
class DatabaseManager:
    # Inicializamos el manager sin conexión todavía
    def __init__(self):
        # Guardamos el engine de SQLAlchemy (se crea en initialize())
        self._engine = None

        # Guardamos la fábrica de sesiones (se crea en initialize())
        self._session_factory = None

    # Abrimos la conexión real a PostgreSQL
    def initialize(self):
        # Registramos que estamos por conectar
        logger.info("Initializing PostgreSQL connection...")

        # Creamos el engine con pool de conexiones. El search_path fija el esquema
        # de esta app dentro de la base compartida de Supabase, así los modelos
        # trabajan con nombres sin calificar. Va en connect_args y no en la URL
        # para que no dependa de cómo se haya pegado el .env.
        self._engine = create_engine(
            settings.DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            connect_args={"options": f"-csearch_path={settings.DB_SCHEMA},public"},
        )

        @event.listens_for(self._engine, "connect")
        def _fijar_search_path(conexion_dbapi, _registro):
            # El paquete de arranque (-csearch_path=...) es la via normal, pero el
            # pooler de Supabase (Supavisor) no lo respeta: con el se conectaba
            # bien y `current_schema()` seguia diciendo «public», asi que cada
            # consulta fallaba con «relation ... does not exist». Este SET corre
            # como una sentencia normal en cuanto se abre la conexion y no
            # depende de que el pooler haga caso al paquete de arranque.
            cursor = conexion_dbapi.cursor()
            cursor.execute(f"SET search_path TO {settings.DB_SCHEMA}, public")
            cursor.close()

            # Sin confirmar, el SET queda dentro de una transaccion abierta:
            # pool_pre_ping prueba la conexion recien creada con un rollback, y
            # ese rollback deshacia el search_path antes de la primera consulta
            # real (Postgres trata SET como transaccional si no se confirma).
            conexion_dbapi.commit()

        # Creamos la fábrica de sesiones ligada a ese engine
        self._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=self._engine)

        # Registramos que la conexión quedó lista, sin exponer credenciales
        logger.info(f"PostgreSQL connected: {settings.DATABASE_URL.split('@')[-1]}")

    # Exponemos el engine para los pocos casos que necesitan SQL crudo
    @property
    def engine(self):
        # Fallamos explícitamente si alguien lo usa antes de initialize()
        if self._engine is None:
            raise RuntimeError("DatabaseManager.initialize() must be called before using the engine")

        # Devolvemos el engine ya construido
        return self._engine

    # Abrimos una sesión nueva para una unidad de trabajo
    def session(self) -> Session:
        # Fallamos explícitamente si alguien la pide antes de initialize()
        if self._session_factory is None:
            raise RuntimeError("DatabaseManager.initialize() must be called before opening sessions")

        # Devolvemos una sesión nueva
        return self._session_factory()

    # Cerramos el pool al apagar la aplicación
    def dispose(self):
        # Solo si llegamos a crear el engine
        if self._engine is not None:
            # Liberamos todas las conexiones del pool
            self._engine.dispose()

            # Registramos el cierre
            logger.info("PostgreSQL connection pool disposed")


# Creamos la instancia única que usa el resto de la app
db_manager = DatabaseManager()


# Fijamos el contexto de RLS al empezar cada transaccion.
#
# Las politicas leen `request.jwt.claims` y evaluan como el rol `authenticated`.
# En un montaje con PostgREST eso lo pone PostgREST; aqui lo pone la propia
# aplicacion, con el mismo resultado: la base decide que filas se ven y cuales
# se pueden tocar, en vez de fiarse de que Python lo haya comprobado.
#
# Va en `after_begin` y no en `get_db` por un motivo concreto: `SET LOCAL` dura
# lo que dure la transaccion, y una ruta que hace `commit()` y sigue
# consultando abriria una transaccion nueva SIN contexto -- y esas consultas
# correrian como `postgres`, que ignora RLS. Enganchado aqui, cada transaccion
# nueva lo recupera sola.
@event.listens_for(Session, "after_begin")
def _fijar_contexto_rls(session, transaction, connection):
    contexto = session.info.get("contexto_rls")

    # Sin contexto la sesion queda elevada, que es lo que necesitan el login
    # (tiene que leer `users` antes de que haya sesion) y la resolucion del
    # propio usuario
    if not contexto:
        return

    connection.exec_driver_sql(
        "select set_config('request.jwt.claims', %s, true)", (contexto,))
    connection.exec_driver_sql("set local role authenticated")


# Definimos la dependencia de FastAPI que entrega una sesión por request
def get_db(request: Request) -> Generator[Session, None, None]:
    # Abrimos la sesión para este request
    db = db_manager.session()

    # Si ya hay usuario resuelto, la sesion trabaja con SUS permisos. El usuario
    # lo resolvio `get_current_user_optional` con una sesion aparte y elevada,
    # que es lo que le permite leer `users` sin depender de RLS.
    cacheado = getattr(request.state, "usuario_resuelto", None)
    usuario = cacheado[1] if cacheado else None

    if usuario and usuario.get("id"):
        db.info["contexto_rls"] = json.dumps({
            "app_user_id": usuario["id"],
            "role": "authenticated",
        })

    # Entregamos la sesión y garantizamos su cierre pase lo que pase
    try:
        # Cedemos el control al handler
        yield db
    finally:
        # Cerramos la sesión al terminar el request
        db.close()
