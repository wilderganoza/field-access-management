"""Catálogo de modelos permitido en Configuración."""

from app.services.openai_config import MODELOS_IA, MODELOS_IA_IDS
from app.services.openai_service import MAX_OUTPUT_POR_MODELO


def test_solo_incluye_modelos_multimodales_con_contexto_de_un_millon():
    assert MODELOS_IA_IDS == {
        "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-5.4", "gpt-5.5",
        "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna",
    }

    for modelo in MODELOS_IA:
        assert modelo["context_window"] >= 1_000_000
        assert not modelo["id"].lower().startswith(("o1", "o3", "o4"))
        if modelo["id"].startswith("gpt-5"):
            assert modelo["reasoning_effort"] == "none"


def test_el_catalogo_no_tiene_ids_duplicados():
    assert len(MODELOS_IA_IDS) == len(MODELOS_IA)


def test_cada_modelo_tiene_limite_de_salida_conocido():
    assert set(MAX_OUTPUT_POR_MODELO) == MODELOS_IA_IDS
    assert max(MAX_OUTPUT_POR_MODELO.values()) == 128_000
