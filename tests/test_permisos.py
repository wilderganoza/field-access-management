"""Pruebas del sistema de perfiles.

Es la lógica que decide qué puede hacer cada persona en cada módulo, y se
consulta desde tres sitios: las plantillas (para pintar un botón), las
dependencias de las rutas (para permitir la llamada) y las políticas RLS (para
permitir la fila). Si los tres no dicen lo mismo, el que manda acaba siendo el
más flojo.

Lo que más importa aquí es la HERENCIA: un submódulo sin permiso propio toma el
del padre. Equivocarse en esa regla concede de más sin que se note, que es la
peor forma de fallar en permisos.

No hace falta base de datos: se prueba sobre el mapa ya resuelto, que es lo que
viaja en la sesión.

Este archivo es el mismo en las dos aplicaciones hermanas.
"""

# Importamos las librerias necesarias
import pytest  # Para los casos con parámetros

from app.models.access import ACCIONES  # El catálogo de acciones
from app.services import permisos  # Lo que se prueba


# Armamos un mapa de permisos como el que devuelve `cargar()`
def mapa(**modulos):
    """Convierte `assets='view,create'` en el mapa que usa `puede()`."""
    resultado = {}

    for clave, concedidas in modulos.items():
        # Las claves con punto se escriben con guion bajo en el argumento
        nombre = clave.replace("__", ".")
        permitidas = set(concedidas.split(",")) if concedidas else set()
        resultado[nombre] = {a: (a in permitidas) for a, _, _ in ACCIONES}

    return resultado


def usuario(**modulos):
    """Un diccionario de sesión con esos permisos."""
    return {"id": 1, "permisos": mapa(**modulos), "tablas": {}}


# --------------------------------------------------------------- lo básico

def test_lo_concedido_se_concede():
    u = usuario(assets="view,create")

    assert permisos.puede(u, "assets", "view")
    assert permisos.puede(u, "assets", "create")


def test_lo_no_concedido_se_niega():
    u = usuario(assets="view")

    assert not permisos.puede(u, "assets", "delete")


def test_un_modulo_que_no_esta_en_el_mapa_se_niega():
    # Un módulo nuevo no debe quedar accesible para todos por olvido
    u = usuario(assets="view")

    assert not permisos.puede(u, "modulo-que-no-existe", "view")


def test_sin_sesion_no_se_puede_nada():
    assert not permisos.puede(None, "assets", "view")
    assert not permisos.puede({}, "assets", "view")


def test_un_usuario_sin_perfil_no_puede_nada():
    # Una cuenta recién creada sin perfil asignado: mínimo privilegio
    assert not permisos.puede({"id": 1, "permisos": {}}, "assets", "view")


def test_una_accion_inventada_se_niega():
    # Un error de programación no debe convertirse en un permiso
    u = usuario(assets="view,create,edit,delete,download")

    assert not permisos.puede(u, "assets", "teletransportar")


# --------------------------------------------------------------- herencia

def test_un_submodulo_hereda_del_padre():
    # Es lo que permite dar acceso a «Assets» entero sin enumerar sus once
    # pestañas
    u = {"id": 1, "permisos": {
        "assets": mapa(assets="view,edit")["assets"],
        # El hijo no tiene fila propia: `cargar()` le habría copiado la del
        # padre, y aquí se comprueba ese mismo efecto
        "assets.wells": mapa(assets="view,edit")["assets"],
    }}

    assert permisos.puede(u, "assets.wells", "edit")


def test_un_submodulo_con_permiso_propio_manda_sobre_el_padre():
    # Afinar hacia abajo tiene que poder quitar, no solo añadir
    u = {"id": 1, "permisos": {
        "assets": mapa(assets="view,edit,delete")["assets"],
        "assets.wells": mapa(assets="view")["assets"],
    }}

    assert permisos.puede(u, "assets.wells", "view")
    assert not permisos.puede(u, "assets.wells", "delete")


# ------------------------------------------------------------ ve_algo (menú)

def test_ve_algo_con_el_modulo_visible():
    assert permisos.ve_algo(usuario(assets="view"), "assets")


def test_ve_algo_por_un_hijo_aunque_el_padre_no_se_vea():
    # Si alguien solo puede ver «Assets > Wells», la sección debe aparecer en el
    # menú: si no, no tendría por dónde llegar
    u = {"id": 1, "permisos": {
        "assets": mapa(assets="")["assets"],
        "assets.wells": mapa(assets="view")["assets"],
    }}

    assert permisos.ve_algo(u, "assets")


def test_no_ve_nada_si_ni_el_padre_ni_los_hijos_son_visibles():
    u = {"id": 1, "permisos": {
        "assets": mapa(assets="")["assets"],
        "assets.wells": mapa(assets="")["assets"],
    }}

    assert not permisos.ve_algo(u, "assets")


def test_ve_algo_no_confunde_modulos_con_prefijo_parecido():
    # «assets» no debe darse por visible porque exista «assets-antiguos»
    u = {"id": 1, "permisos": {
        "assets": mapa(assets="")["assets"],
        "assets-antiguos": mapa(assets="view")["assets"],
    }}

    assert not permisos.ve_algo(u, "assets")


def test_sin_sesion_no_ve_nada():
    assert not permisos.ve_algo(None, "assets")


# ------------------------------------------------------ permisos por tabla

def test_puede_tabla_resuelve_por_el_mapa_de_tablas():
    # Es como autoriza el mantenedor genérico: sabe su tabla, no su módulo
    u = usuario(assets__wells="view,delete")
    u["tablas"] = {"wells": "assets.wells"}

    assert permisos.puede_tabla(u, "wells", "delete")


def test_una_tabla_sin_modulo_se_niega():
    # Deliberado: preferimos que una tabla nueva quede inaccesible hasta que se
    # le asigne módulo, y no accesible para todos por olvido
    u = usuario(assets="view,create,edit,delete,download")
    u["tablas"] = {}

    assert not permisos.puede_tabla(u, "wells", "view")


def test_puede_tabla_sin_sesion_se_niega():
    assert not permisos.puede_tabla(None, "wells", "view")


# -------------------------------------------------------------- el catálogo

def test_las_cinco_acciones_estan_declaradas():
    # La pantalla, el guardián de las rutas y las políticas leen esta misma
    # lista: si alguien añade una acción, aparece en los tres a la vez
    claves = [a for a, _, _ in ACCIONES]

    assert claves == ["view", "create", "edit", "delete", "download"]


@pytest.mark.parametrize("clave,etiqueta,columna", ACCIONES)
def test_cada_accion_apunta_a_su_columna(clave, etiqueta, columna):
    # La columna se usa con getattr sobre la fila de permisos: un nombre mal
    # escrito aquí concede o niega la acción equivocada, en silencio
    assert columna == f"can_{clave}"
    assert etiqueta
