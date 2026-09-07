"""Cifrado de secretos persistidos por la aplicación."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


PREFIJO = "enc:v1:"


def _fernet() -> Fernet:
    """Deriva una clave de cifrado separada a partir del secreto del servidor."""
    material = (settings.SECRET_KEY + "|fda-global-settings").encode("utf-8")
    clave = base64.urlsafe_b64encode(hashlib.sha256(material).digest())
    return Fernet(clave)


def cifrar(valor: str) -> str:
    if not valor:
        return ""
    token = _fernet().encrypt(valor.encode("utf-8")).decode("ascii")
    return PREFIJO + token


def descifrar(valor: str) -> str:
    """Descifra valores actuales y admite texto legado para migración suave."""
    if not valor:
        return ""
    if not valor.startswith(PREFIJO):
        return valor

    try:
        return _fernet().decrypt(valor[len(PREFIJO):].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""
