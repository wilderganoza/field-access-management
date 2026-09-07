"""Resolución de la credencial de OpenAI guardada en configuración."""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.analysis import GlobalSetting
from app.services.secretos import descifrar


OPENAI_KEY_SETTING = "openai_api_key"
IA_MODEL_SETTING = "openai_model"

# Modelos vigentes con entrada de texto e imagen y una ventana aproximada de un
# millón de tokens. En las familias que pueden razonar fijamos `none`: así se
# usan como modelos directos y nunca consumen tokens de razonamiento.
# Usamos aliases estables; las versiones fechadas multiplicarían equivalentes.
MODELOS_IA = (
    {
        "id": "gpt-4.1",
        "name": "GPT-4.1",
        "description": "1.05 M de contexto · 32 mil de salida",
        "context_window": 1047576,
        "max_output": 32768,
        "reasoning_effort": None,
    },
    {
        "id": "gpt-4.1-mini",
        "name": "GPT-4.1 mini",
        "description": "1.05 M de contexto · 32 mil de salida",
        "context_window": 1047576,
        "max_output": 32768,
        "reasoning_effort": None,
    },
    {
        "id": "gpt-4.1-nano",
        "name": "GPT-4.1 nano",
        "description": "1.05 M de contexto · 32 mil de salida",
        "context_window": 1047576,
        "max_output": 32768,
        "reasoning_effort": None,
    },
    {
        "id": "gpt-5.4",
        "name": "GPT-5.4",
        "description": "1.05 M de contexto · 128 mil de salida",
        "context_window": 1050000,
        "max_output": 128000,
        "reasoning_effort": "none",
    },
    {
        "id": "gpt-5.5",
        "name": "GPT-5.5",
        "description": "1.05 M de contexto · 128 mil de salida",
        "context_window": 1050000,
        "max_output": 128000,
        "reasoning_effort": "none",
    },
    {
        "id": "gpt-5.6-sol",
        "name": "GPT-5.6 Sol",
        "description": "1.05 M de contexto · 128 mil de salida",
        "context_window": 1050000,
        "max_output": 128000,
        "reasoning_effort": "none",
    },
    {
        "id": "gpt-5.6-terra",
        "name": "GPT-5.6 Terra",
        "description": "1.05 M de contexto · 128 mil de salida",
        "context_window": 1050000,
        "max_output": 128000,
        "reasoning_effort": "none",
    },
    {
        "id": "gpt-5.6-luna",
        "name": "GPT-5.6 Luna",
        "description": "1.05 M de contexto · 128 mil de salida",
        "context_window": 1050000,
        "max_output": 128000,
        "reasoning_effort": "none",
    },
)

MODELOS_IA_IDS = frozenset(modelo["id"] for modelo in MODELOS_IA)
MODELOS_IA_POR_ID = {modelo["id"]: modelo for modelo in MODELOS_IA}


def clave_guardada(db: Session) -> str:
    fila = db.query(GlobalSetting).filter(GlobalSetting.key == OPENAI_KEY_SETTING).first()
    return descifrar(fila.value) if fila else ""


def obtener_clave_openai(db: Session) -> str:
    """Prioriza la interfaz; conserva `.env` como alternativa de despliegue."""
    return clave_guardada(db) or settings.OPENAI_API_KEY.strip()


def obtener_modelo_ia(db: Session) -> str:
    fila = db.query(GlobalSetting).filter(GlobalSetting.key == IA_MODEL_SETTING).first()
    elegido = fila.value.strip() if fila else settings.OPENAI_MODEL.strip()
    return elegido if elegido in MODELOS_IA_IDS else "gpt-4.1"


def origen_clave_openai(db: Session) -> str:
    if clave_guardada(db):
        return "interfaz"
    if settings.OPENAI_API_KEY.strip():
        return "servidor"
    return ""
