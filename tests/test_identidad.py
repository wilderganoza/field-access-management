"""Pruebas de la identidad propia: contraseñas y token de sesión.

Al dejar Supabase Auth, esta aplicación pasó a custodiar sus propias
credenciales. Eso significa que un fallo aquí no lo detecta nadie más: no hay un
proveedor detrás que rechace lo que nosotros aceptemos por error.

Lo que se sostiene aquí es lo que ya falló una vez en este código —se aceptaban
tokens sin comprobar la firma— y lo que no debe volver a fallar.

No hace falta base de datos: todo esto es lógica sobre bytes y cadenas.

Este archivo es el mismo en Field Data Platform y en Verificación de Permisos.
"""

# Importamos las librerias necesarias
import time  # Para fabricar tokens vencidos

import jwt  # Para forjar tokens de prueba
import pytest  # Para los casos con parámetros

from app.core import security  # Lo que se prueba
from app.core.config import settings  # Para fijar el secreto de firma

# Un secreto de prueba. No es el de ningún proyecto: se fija en cada prueba.
SECRETO = "secreto-de-prueba-para-las-pruebas"


@pytest.fixture(autouse=True)
def con_secreto(monkeypatch):
    """Fija un secreto de firma conocido para toda la prueba."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", SECRETO)


# ------------------------------------------------------------ contraseñas

def test_una_contrasena_se_verifica_contra_su_hash():
    # Lo mínimo: lo que se guarda sirve para comprobar lo que se escribe
    hashed = security.hash_password("MiClaveSegura123")

    assert security.verify_password("MiClaveSegura123", hashed)


def test_una_contrasena_distinta_no_valida():
    hashed = security.hash_password("MiClaveSegura123")

    assert not security.verify_password("otra-cosa", hashed)


def test_el_hash_no_contiene_la_contrasena():
    # Suena obvio, pero es lo que separa un hash de una codificación
    hashed = security.hash_password("MiClaveSegura123")

    assert "MiClaveSegura123" not in hashed


def test_dos_hashes_de_la_misma_contrasena_son_distintos():
    # argon2 genera una sal por hash. Sin sal, dos personas con la misma
    # contraseña tendrían el mismo hash y una tabla precalculada las abriría
    # a las dos de una vez.
    a = security.hash_password("misma")
    b = security.hash_password("misma")

    assert a != b
    assert security.verify_password("misma", a)
    assert security.verify_password("misma", b)


def test_un_hash_vacio_no_valida_nada():
    # Una cuenta sin contraseña puesta no es una cuenta que acepte cualquiera
    assert not security.verify_password("", "")
    assert not security.verify_password("loquesea", "")


def test_un_hash_de_otro_algoritmo_no_valida_ni_revienta():
    # La versión Flask dejó hashes scrypt. No deben validar, y sobre todo no
    # deben lanzar: una excepción aquí sería un 500 en el login.
    scrypt = "scrypt:32768:8:1$sal$dedodedo"

    assert not security.verify_password("loquesea", scrypt)


def test_un_hash_de_otro_algoritmo_pide_rehash():
    assert security.needs_rehash("scrypt:32768:8:1$sal$dedodedo")


def test_un_hash_recien_hecho_no_pide_rehash():
    assert not security.needs_rehash(security.hash_password("x"))


# ------------------------------------------------------------------ token

def test_el_token_lleva_lo_que_postgrest_necesita():
    claims = security.decode_claims(security.create_access_token(42))

    # Sin `role: authenticated`, PostgREST trata la petición como anónima y RLS
    # la rechaza entera
    assert claims["role"] == "authenticated"

    # Y `app_user_id` es lo que leen nuestras políticas. Va aparte de `sub`
    # porque `auth.uid()` castea a uuid y el nuestro es entero.
    assert claims["app_user_id"] == 42
    assert claims["sub"] == "42"


def test_un_token_nuestro_se_acepta():
    assert security.decode_claims(security.create_access_token(1)) is not None


def test_un_token_firmado_con_otro_secreto_se_rechaza():
    # Es el agujero que tuvo este código: se decodificaba sin comprobar la
    # firma, así que cualquiera se fabricaba una sesión de administrador
    forjado = jwt.encode(
        {"sub": "1", "app_user_id": 1, "role": "authenticated",
         "exp": int(time.time()) + 3600},
        "el-secreto-del-atacante", algorithm="HS256")

    assert security.decode_claims(forjado) is None


def test_un_token_sin_firma_se_rechaza():
    # `alg: none` es la forma clásica de saltarse una verificación mal hecha
    sin_firma = jwt.encode(
        {"sub": "1", "app_user_id": 1, "exp": int(time.time()) + 3600},
        None, algorithm="none")

    assert security.decode_claims(sin_firma) is None


def test_un_token_vencido_se_rechaza():
    vencido = jwt.encode(
        {"sub": "1", "app_user_id": 1, "role": "authenticated",
         "exp": int(time.time()) - 10},
        SECRETO, algorithm="HS256")

    assert security.decode_claims(vencido) is None


def test_un_token_manipulado_se_rechaza():
    # Se cambia un byte del payload sin rehacer la firma
    bueno = security.create_access_token(1)
    cabecera, payload, firma = bueno.split(".")
    roto = f"{cabecera}.{payload[:-2]}XX.{firma}"

    assert security.decode_claims(roto) is None


@pytest.mark.parametrize("basura", ["", "  ", "no-es-un-token", "a.b.c"])
def test_una_cadena_cualquiera_no_es_una_sesion(basura):
    assert security.decode_claims(basura) is None


def test_sin_secreto_no_se_acepta_ningun_token(monkeypatch):
    # Un token que no se puede verificar no se acepta jamas: es preferible que
    # no entre nadie a que entre cualquiera
    bueno = security.create_access_token(1)

    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "")

    assert security.decode_claims(bueno) is None


def test_sin_secreto_no_se_puede_emitir(monkeypatch):
    # Emitir un token que la base no va a aceptar solo produce sesiones que
    # fallan mas tarde y en otro sitio
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "")

    with pytest.raises(security.AuthError):
        security.create_access_token(1)


# --------------------------------------------------- identificador de usuario

def test_se_lee_el_identificador_de_los_claims():
    claims = security.decode_claims(security.create_access_token(7))

    assert security.id_de_usuario(claims) == 7


@pytest.mark.parametrize("claims", [None, {}, {"sub": "no-es-un-numero"},
                                    {"app_user_id": None}])
def test_unos_claims_sin_identificador_legible_no_dan_usuario(claims):
    assert security.id_de_usuario(claims) is None


# ------------------------------------------------------------------ tiempos

def test_quemar_tiempo_no_lanza():
    # Se llama cuando el correo no existe, para que la respuesta tarde lo mismo
    # que con una cuenta real. Si lanzara, delataria el caso justo al reves.
    security.quemar_tiempo()


def test_un_correo_inexistente_cuesta_lo_mismo_que_uno_real():
    """El tiempo no debe delatar qué cuentas existen.

    Se compara la comprobación real contra el señuelo. No se exige igualdad
    exacta —eso sería una prueba inestable— sino el mismo orden de magnitud:
    lo que se evita es la diferencia entre microsegundos y decenas de
    milisegundos, que sí se mide desde fuera.
    """
    hashed = security.hash_password("una-clave")

    t0 = time.perf_counter()
    security.verify_password("incorrecta", hashed)
    real = time.perf_counter() - t0

    t0 = time.perf_counter()
    security.quemar_tiempo()
    senuelo = time.perf_counter() - t0

    # Dentro de un factor de diez en cualquier sentido
    assert 0.1 < (senuelo / real) < 10
