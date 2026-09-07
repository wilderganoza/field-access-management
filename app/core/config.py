# Importamos las librerias necesarias
from typing import List  # Tipo para anotar la lista de orígenes CORS
from pydantic_settings import BaseSettings  # Base que lee la configuración desde variables de entorno / .env
from pydantic import Field, model_validator  # Field para declarar cada setting, model_validator para validar tras cargar todo


# Definimos el valor placeholder de SECRET_KEY, para poder detectar si nunca se cambió
DEFAULT_SECRET_KEY = "change-this-secret-key-in-production"


# Declaramos la configuración global de la aplicación, cargada desde variables de entorno o .env
class Settings(BaseSettings):
    # Guardamos el nombre de la aplicación
    APP_NAME: str = Field(default="Verificación de Permisos")

    # Guardamos la versión de la aplicación
    APP_VERSION: str = Field(default="1.0.0")

    # Guardamos si el modo debug está activo (recarga automática, logs más verbosos)
    DEBUG: bool = Field(default=False)

    # Guardamos el entorno actual (development | production)
    ENVIRONMENT: str = Field(default="production")

    # Guardamos el host donde escucha el servidor
    HOST: str = Field(default="0.0.0.0")

    # Guardamos el puerto donde escucha el servidor
    PORT: int = Field(default=8001)

    # Guardamos la URL de conexión a PostgreSQL (Supabase)
    DATABASE_URL: str = Field(default="postgresql://postgres:postgres@localhost:5432/postgres")

    # Guardamos el esquema donde vive esta app dentro de la base compartida.
    # Las cinco aplicaciones comparten un mismo proyecto y se separan por esquema.
    DB_SCHEMA: str = Field(default="fda")

    # Guardamos la URL del proyecto Supabase (para Auth y Storage)
    SUPABASE_URL: str = Field(default="")

    # Guardamos la clave publicable de Supabase (segura de exponer, va al navegador)
    SUPABASE_PUBLISHABLE_KEY: str = Field(default="")

    # Guardamos la clave de servicio, que salta las políticas RLS y permite crear
    # y borrar cuentas. Es la credencial más sensible de la aplicación: nunca
    # debe llegar al navegador ni quedar en el repositorio. Si está vacía, la
    # pantalla de usuarios funciona en modo lectura en vez de fallar.
    SUPABASE_SERVICE_ROLE_KEY: str = Field(default="")

    # Guardamos el secreto con el que Supabase firma los access token. Sin esto
    # no se puede comprobar la firma, y un token cualquiera valdria. Se saca del
    # panel del proyecto (Settings -> API -> JWT Secret). Si el proyecto firma
    # con claves asimetricas (ES256/RS256) no hace falta: se comprueba contra su
    # JWKS, que se lee de SUPABASE_URL.
    SUPABASE_JWT_SECRET: str = Field(default="")

    # Cuanto dura una sesion antes de tener que volver a entrar, en minutos.
    # Ocho horas: una jornada. Mas corto obliga a reautenticarse a media tarde;
    # mas largo deja tokens vivos toda la noche en equipos compartidos.
    SESSION_TTL_MINUTES: int = Field(default=480)

    # Guardamos el nombre de la cookie donde viaja el token de sesión
    SESSION_COOKIE_NAME: str = Field(default="fda_session")

    # Guardamos el nombre de la cookie donde viaja el refresh token de Supabase
    REFRESH_COOKIE_NAME: str = Field(default="fda_refresh")

    # Guardamos si las cookies exigen HTTPS (desactivar solo en desarrollo local)
    COOKIE_SECURE: bool = Field(default=True)

    # Guardamos la clave de OpenAI. A diferencia de la versión React, vive solo en
    # el servidor: el navegador nunca la ve.
    OPENAI_API_KEY: str = Field(default="")

    # Guardamos el modelo de OpenAI usado para el análisis documental
    OPENAI_MODEL: str = Field(default="gpt-4.1")

    # Guardamos los orígenes permitidos para CORS. La app se sirve same-origin
    # (Jinja2 + HTMX desde este mismo proceso), así que por defecto va vacío.
    CORS_ORIGINS: List[str] = Field(default=[])

    # Guardamos la clave secreta usada para firmar cookies propias
    SECRET_KEY: str = Field(default=DEFAULT_SECRET_KEY)

    # Guardamos el nivel de logging de la aplicación
    LOG_LEVEL: str = Field(default="INFO")

    # Guardamos el tamaño máximo aceptado por archivo subido, en megabytes
    MAX_UPLOAD_MB: int = Field(default=100)

    # Validamos, una vez cargados todos los settings, que la app no arranque en
    # producción con la SECRET_KEY placeholder
    @model_validator(mode="after")
    def check_secret_key_in_production(self) -> "Settings":
        # Detectamos la combinación peligrosa: producción + SECRET_KEY nunca configurada
        if self.ENVIRONMENT == "production" and not self.DEBUG and self.SECRET_KEY == DEFAULT_SECRET_KEY:
            # Rechazamos el arranque en vez de servir con una clave insegura conocida
            raise ValueError("SECRET_KEY must be set via environment variable in production; refusing to start with the default placeholder key")

        # Devolvemos la instancia validada
        return self

    # Validamos que en produccion se pueda comprobar la firma de los tokens
    @model_validator(mode="after")
    def check_jwt_verification_in_production(self) -> "Settings":
        # Hacen falta dos cosas, y con una basta segun como firme el proyecto: el
        # secreto compartido (HS256) o la URL desde la que leer el JWKS
        # (ES256/RS256). Sin ninguna no hay forma de comprobar una firma, y un
        # token fabricado a mano entraria como sesion valida.
        if (self.ENVIRONMENT == "production" and not self.DEBUG
                and not self.SUPABASE_JWT_SECRET and not self.SUPABASE_URL):
            raise ValueError(
                "In production set SUPABASE_JWT_SECRET (projects signing with HS256; "
                "Supabase > Settings > API > JWT Secret) or SUPABASE_URL (projects "
                "signing with asymmetric keys, verified against the project JWKS). "
                "Without either, access token signatures cannot be verified and a "
                "forged token would be accepted as a valid session."
            )

        # Devolvemos la instancia validada
        return self

    # Configuramos cómo pydantic-settings carga estos valores
    class Config:
        # Leemos las variables desde el archivo .env si existe
        env_file = ".env"

        # Exigimos que los nombres de las variables respeten mayúsculas/minúsculas
        case_sensitive = True

        # Ignoramos las variables que no declaramos aquí. Mientras dure la
        # migración, este .env lo comparten la app Express que sale (DB_HOST,
        # JWT_SECRET, SERVER_PORT...) y esta. Sin esto, pydantic aborta el
        # arranque al toparse con las claves de la otra.
        extra = "ignore"


# Creamos la instancia única de configuración que usa el resto de la app
settings = Settings()
