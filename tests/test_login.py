"""Pruebas de las defensas del login.

Dos cosas que ya fallaron en este código y no deben volver a fallar:

  - `next` se usaba tal cual en la redirección posterior a entrar, así que un
    enlace a `/login?next=https://sitio-falso.example` sacaba al usuario del
    sitio justo después de autenticarse.
  - No había ningún freno a probar contraseñas: se podían intentar tan rápido
    como aguantara el servidor.

Este archivo es el mismo en las dos aplicaciones hermanas.
"""

# Importamos las librerias necesarias
import types  # Para fabricar un request de mentira

import pytest  # Para los casos con parámetros

from app.web import auth  # Lo que se prueba


# --------------------------------------------------------- destino seguro

@pytest.mark.parametrize("externo", [
    "https://sitio-falso.example",
    "http://sitio-falso.example/algo",
    # Relativa al protocolo: el navegador la resuelve como otro sitio
    "//sitio-falso.example",
    # Algunos navegadores normalizan la barra invertida a `//`
    "/\\sitio-falso.example",
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
])
def test_un_destino_externo_se_sustituye_por_la_raiz(externo):
    assert auth.destino_seguro(externo) == "/"


@pytest.mark.parametrize("interno", [
    "/", "/losses", "/assets?tab=wells", "/admin/roles/1",
    "/wells/export?desde=2020-01-01&sort=name",
])
def test_un_destino_interno_se_conserva(interno):
    assert auth.destino_seguro(interno) == interno


@pytest.mark.parametrize("vacio", ["", "   ", None])
def test_un_destino_vacio_lleva_a_la_raiz(vacio):
    assert auth.destino_seguro(vacio) == "/"


# ---------------------------------------------------- freno a la fuerza bruta

def request_de(ip="10.0.0.1"):
    """Un request de mentira con la IP que se le indique."""
    return types.SimpleNamespace(client=types.SimpleNamespace(host=ip))


@pytest.fixture(autouse=True)
def sin_intentos_previos():
    """Cada prueba empieza con el contador limpio."""
    auth._fallos.clear()
    yield
    auth._fallos.clear()


def test_los_primeros_intentos_pasan():
    clave = auth._clave_intentos(request_de(), "alguien@ejemplo.com")

    for _ in range(auth.INTENTOS_MAX):
        assert not auth._demasiados_intentos(clave)
        auth._anotar_fallo(clave)


def test_al_pasarse_del_limite_se_bloquea():
    clave = auth._clave_intentos(request_de(), "alguien@ejemplo.com")

    for _ in range(auth.INTENTOS_MAX):
        auth._anotar_fallo(clave)

    assert auth._demasiados_intentos(clave)


def test_entrar_bien_limpia_el_contador():
    # Quien sabe su contraseña no debe notar nunca el freno
    clave = auth._clave_intentos(request_de(), "alguien@ejemplo.com")

    for _ in range(auth.INTENTOS_MAX):
        auth._anotar_fallo(clave)

    auth._limpiar_intentos(clave)

    assert not auth._demasiados_intentos(clave)


def test_el_freno_no_alcanza_a_otra_cuenta():
    # Bloquear a todo el mundo porque alguien ataca una cuenta sería un modo
    # cómodo de dejar la aplicación fuera de servicio
    atacada = auth._clave_intentos(request_de(), "victima@ejemplo.com")
    otra = auth._clave_intentos(request_de(), "otra@ejemplo.com")

    for _ in range(auth.INTENTOS_MAX):
        auth._anotar_fallo(atacada)

    assert auth._demasiados_intentos(atacada)
    assert not auth._demasiados_intentos(otra)


def test_el_freno_no_alcanza_a_otra_ip():
    misma_cuenta = "alguien@ejemplo.com"
    desde_a = auth._clave_intentos(request_de("10.0.0.1"), misma_cuenta)
    desde_b = auth._clave_intentos(request_de("10.0.0.2"), misma_cuenta)

    for _ in range(auth.INTENTOS_MAX):
        auth._anotar_fallo(desde_a)

    assert auth._demasiados_intentos(desde_a)
    assert not auth._demasiados_intentos(desde_b)


def test_el_correo_no_distingue_mayusculas_en_el_contador():
    # Si no, alternar mayúsculas multiplicaría los intentos disponibles
    a = auth._clave_intentos(request_de(), "Alguien@Ejemplo.com")
    b = auth._clave_intentos(request_de(), "alguien@ejemplo.com  ")

    assert a == b


def test_sin_ip_el_contador_sigue_protegiendo_la_cuenta():
    # Tras algunos proxies no hay `client`. Se cuenta solo por correo, que es
    # peor que nada pero sigue frenando el ataque a una cuenta concreta.
    sin_cliente = types.SimpleNamespace(client=None)
    clave = auth._clave_intentos(sin_cliente, "alguien@ejemplo.com")

    assert "alguien@ejemplo.com" in clave

    for _ in range(auth.INTENTOS_MAX):
        auth._anotar_fallo(clave)

    assert auth._demasiados_intentos(clave)
