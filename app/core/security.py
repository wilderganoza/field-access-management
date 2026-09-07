"""Autenticación propia de la aplicación.

Antes esto hablaba con Supabase Auth (GoTrue): el usuario vivía allí y aquí solo
quedaba un perfil. Ahora la aplicación es su propio servidor de identidad y la
tabla `users` de su esquema es la única fuente de verdad.

Lo que NO cambia es quién valida el token cuando se consulta la base: PostgREST
solo acepta un JWT firmado con el secreto del proyecto, y `auth.uid()` dentro de
una política RLS lee sus claims. Por eso los tokens que emitimos van firmados
con ese mismo secreto y llevan `role: authenticated`. La aplicación decide QUIÉN
eres; la base sigue decidiendo QUÉ puedes ver.

Este archivo es byte a byte el mismo en Field Data Platform y en Verificación de
Permisos: son aplicaciones hermanas y la identidad se resuelve igual en ambas.
"""

# Importamos las librerias necesarias
from datetime import datetime, timedelta, timezone  # Para fechar y caducar el token
from typing import Any, Dict, Optional  # Tipos

import jwt  # Para firmar y verificar el token de sesión
from argon2 import PasswordHasher  # Hash de contraseñas
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

from app.core.config import settings  # Secreto de firma y duración de la sesión
from app.core.logging import get_logger  # Para registrar los fallos

# Creamos el logger de este módulo
logger = get_logger(__name__)


# Definimos el error que lanzamos cuando las credenciales no son válidas
class AuthError(Exception):
    """Credenciales inválidas, cuenta desactivada o sesión no renovable."""


# El algoritmo con el que se firma. HS256 es lo que espera PostgREST del secreto
# del proyecto; cambiarlo aquí haría que la base rechazara nuestros tokens.
ALGORITMO = "HS256"

# Configuramos argon2 con los parámetros por defecto de la librería, que siguen
# la recomendación vigente de OWASP. Se dejan explícitos para que se vean y para
# que cambiarlos sea una decisión, no un efecto de actualizar una dependencia.
_hasher = PasswordHasher(
    time_cost=3,        # Iteraciones
    memory_cost=65536,  # 64 MiB: lo que encarece el ataque por GPU
    parallelism=4,      # Hilos
)


# Convertimos una contraseña en su hash
def hash_password(plana: str) -> str:
    """El hash argon2id de esa contraseña, con su sal incluida."""
    # argon2 genera una sal aleatoria por hash y la guarda dentro del resultado
    return _hasher.hash(plana)


# Comprobamos una contraseña contra su hash
def verify_password(plana: str, hasheada: str) -> bool:
    """Cierto si la contraseña corresponde al hash. Nunca lanza."""
    # Un hash vacío es una cuenta sin contraseña puesta: no valida nada
    if not hasheada:
        return False

    try:
        # argon2 compara en tiempo constante
        return _hasher.verify(hasheada, plana)

    # Contraseña incorrecta, hash corrupto o de otro algoritmo (el scrypt que
    # dejó la versión Flask): en todos los casos, no valida
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


# Indicamos si conviene volver a hashear con los parámetros actuales
def needs_rehash(hasheada: str) -> bool:
    """Cierto si el hash se hizo con parámetros más flojos que los de ahora.

    Se comprueba al entrar: si los parámetros de argon2 se endurecen, la
    contraseña se rehashea con la que el usuario acaba de escribir, sin pedirle
    nada. Un hash de otro algoritmo también cuenta: hay que reemplazarlo.
    """
    # Sin hash no hay nada que rehashear
    if not hasheada:
        return False

    try:
        return _hasher.check_needs_rehash(hasheada)

    # Un hash que argon2 no reconoce hay que reemplazarlo igualmente
    except InvalidHash:
        return True


# Hash de descarte, para que un correo inexistente cueste lo mismo que uno real
_HASH_SEÑUELO = _hasher.hash("contraseña-que-no-es-de-nadie")


# Gastamos el mismo tiempo aunque la cuenta no exista
def quemar_tiempo() -> None:
    """Verifica contra un hash de descarte.

    Sin esto, un correo inexistente responde en microsegundos y uno real tarda
    los ~50 ms de argon2: la diferencia se mide desde fuera y permite averiguar
    qué cuentas existen sin acertar ni una contraseña.
    """
    # El resultado no importa: lo que importa es haber tardado lo mismo
    verify_password("x", _HASH_SEÑUELO)


# Emitimos el token de sesión
def create_access_token(user_id: int, minutos: Optional[int] = None,
                        extra: Optional[Dict[str, Any]] = None) -> str:
    """El JWT de esa sesión, firmado con el secreto del proyecto."""
    # Sin secreto no se puede firmar nada que PostgREST vaya a aceptar
    if not settings.SUPABASE_JWT_SECRET:
        raise AuthError(
            "SUPABASE_JWT_SECRET no está configurado: sin él no se pueden emitir "
            "sesiones que la base acepte"
        )

    ahora = datetime.now(timezone.utc)
    vida = minutos if minutos is not None else settings.SESSION_TTL_MINUTES

    claims: Dict[str, Any] = {
        # `sub` va como texto por el estándar; PostgREST lo expone tal cual
        "sub": str(user_id),
        # PostgREST cambia a este rol de Postgres al atender la petición. Sin
        # este claim la trata como anónima y RLS la rechaza entera.
        "role": "authenticated",
        # El identificador que leen nuestras políticas. Va aparte de `sub`
        # porque `auth.uid()` castea a uuid y el nuestro es entero.
        "app_user_id": int(user_id),
        "iat": ahora,
        "exp": ahora + timedelta(minutes=vida),
    }

    # Lo que quiera añadir el llamador, sin poder pisar lo de arriba
    for clave, valor in (extra or {}).items():
        claims.setdefault(clave, valor)

    return jwt.encode(claims, settings.SUPABASE_JWT_SECRET, algorithm=ALGORITMO)


# Leemos los claims de un token COMPROBANDO SU FIRMA
def decode_claims(access_token: str) -> Optional[Dict[str, Any]]:
    """Los claims si el token es nuestro y sigue vigente, o None."""
    # Un token vacío no tiene claims que leer
    if not access_token:
        return None

    # Sin secreto no se puede comprobar la firma, y un token sin verificar no
    # se acepta jamás: es exactamente el agujero que esto viene a cerrar
    if not settings.SUPABASE_JWT_SECRET:
        logger.error(
            "SUPABASE_JWT_SECRET sin configurar: no se puede verificar la firma "
            "de la sesión, así que se rechaza"
        )
        return None

    try:
        return jwt.decode(
            access_token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=[ALGORITMO],
            # La audiencia no se exige: lo que no se negocia es la firma
            options={"verify_signature": True, "verify_exp": True, "verify_aud": False},
        )

    # Firma inválida, token vencido o malformado: no hay sesión
    except jwt.PyJWTError as exc:
        logger.info(f"Sesión rechazada ({type(exc).__name__})")
        return None


# Sacamos de los claims el identificador del usuario local
def id_de_usuario(claims: Optional[Dict[str, Any]]) -> Optional[int]:
    """El id de `users` que lleva el token, o None si no es legible."""
    if not claims:
        return None

    crudo = claims.get("app_user_id", claims.get("sub"))

    try:
        return int(crudo)

    # Un `sub` que no sea un entero no es de esta aplicación
    except (TypeError, ValueError):
        return None
