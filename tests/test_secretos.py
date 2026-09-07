"""Los secretos de Configuración nunca se persisten en texto claro."""

from app.services.secretos import PREFIJO, cifrar, descifrar


def test_cifrado_y_descifrado_de_un_secreto():
    original = "sk-proj-ejemplo-que-no-es-una-clave-real"
    guardado = cifrar(original)

    assert guardado.startswith(PREFIJO)
    assert original not in guardado
    assert descifrar(guardado) == original


def test_un_token_cifrado_corrupto_no_se_usa():
    assert descifrar(PREFIJO + "token-invalido") == ""
