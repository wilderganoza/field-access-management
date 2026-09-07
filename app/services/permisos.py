"""Qué puede hacer cada perfil en cada módulo.

Los permisos se resuelven UNA vez por petición y viajan dentro de `current_user`.
Son pocos —el perfil más amplio de FDP tiene 55 filas— así que traerlos enteros
cuesta una consulta y evita una por cada botón que la plantilla quiere pintar.

La herencia es del padre al hijo: si el perfil no declara nada para
«assets.wells» pero sí para «assets», vale la del padre. Eso permite dar acceso
grueso sin enumerar los treinta y cuatro submódulos, y afinar solo donde hace
falta.

Este archivo es el mismo en Field Data Platform y en Verificación de Permisos.
"""

# Importamos las librerias necesarias
from typing import Dict, Optional  # Tipos

from sqlalchemy.orm import Session  # Sesión de base de datos

from app.core.logging import get_logger  # Para registrar los fallos
from app.models.access import ACCIONES, Module, RolePermission  # Catálogo y matriz

# Creamos el logger de este módulo
logger = get_logger(__name__)

# Las claves de acción, sacadas del catálogo para no repetirlas
CLAVES_ACCION = tuple(clave for clave, _, _ in ACCIONES)

# Lo que se responde cuando no hay nada concedido
NINGUNO: Dict[str, bool] = {clave: False for clave in CLAVES_ACCION}


# Cargamos el mapa de permisos de un perfil
def cargar(db: Session, role_id: Optional[int]) -> Dict[str, Dict[str, bool]]:
    """Los permisos de ese perfil, por clave de módulo.

    Devuelve el mapa ya resuelto con la herencia aplicada, de modo que quien
    pregunta no tiene que saber que existen padres e hijos.
    """
    # Sin perfil no se concede nada. Es el caso de una cuenta recién creada a
    # la que todavía no se le asignó uno, y el mínimo privilegio es no poder.
    if role_id is None:
        return {}

    try:
        # Traemos el árbol y la matriz de una vez
        modulos = db.query(Module).all()
        filas = (db.query(RolePermission)
                 .filter(RolePermission.role_id == role_id).all())

    # Si la base no responde no se conceden permisos: negar de más es
    # recuperable, conceder de más no
    except Exception as exc:
        logger.warning(f"No se pudieron cargar los permisos: {type(exc).__name__}: {exc}")
        return {}

    # Indexamos para poder recorrer el árbol sin volver a la base
    por_id = {m.id: m for m in modulos}
    concedido = {f.module_id: f for f in filas}

    mapa: Dict[str, Dict[str, bool]] = {}

    for modulo in modulos:
        # Se busca permiso propio y, si no lo hay, el del padre. Se sube la
        # cadena entera por si algún día hay tres niveles.
        actual = modulo
        fila = None

        while actual is not None:
            fila = concedido.get(actual.id)

            if fila is not None:
                break

            actual = por_id.get(actual.parent_id) if actual.parent_id else None

        mapa[modulo.key] = (
            {clave: bool(getattr(fila, columna))
             for clave, _, columna in ACCIONES}
            if fila is not None else dict(NINGUNO)
        )

    return mapa


# Cargamos con que modulo se gobierna cada tabla
def tablas_por_modulo(db: Session) -> Dict[str, str]:
    """El modulo que gobierna cada tabla, por nombre de tabla.

    Lo necesita el guardian de las rutas: una ruta del mantenedor generico sabe
    sobre que TABLA opera, no sobre que modulo, y es `modules.table_name` quien
    los ata. Es el mismo vinculo que usan las politicas RLS, para que servidor y
    base no puedan discrepar.
    """
    try:
        return {m.table_name: m.key
                for m in db.query(Module).filter(Module.table_name.isnot(None)).all()}

    # Sin el mapa no se puede autorizar nada por tabla: se niega
    except Exception as exc:
        logger.warning(f"No se pudo cargar el mapa de tablas: {type(exc).__name__}: {exc}")
        return {}


# Preguntamos por un permiso indicando la tabla en vez del modulo
def puede_tabla(usuario: Optional[dict], tabla: str, accion: str = "view") -> bool:
    """Cierto si puede esa accion sobre el modulo que gobierna esa tabla."""
    if not usuario:
        return False

    modulo = (usuario.get("tablas") or {}).get(tabla)

    # Una tabla sin modulo no la gobierna nadie, asi que no se concede. Es
    # deliberado: preferimos que una tabla nueva quede inaccesible hasta que se
    # le asigne modulo, y no accesible para todos por olvido.
    if modulo is None:
        return False

    return puede(usuario, modulo, accion)


# Preguntamos por un permiso concreto
def puede(usuario: Optional[dict], modulo: str, accion: str = "view") -> bool:
    """Cierto si ese usuario puede hacer esa acción en ese módulo.

    Se le pasa el diccionario de sesión entero, no el mapa, para que la llamada
    se lea igual en las rutas y en las plantillas: `puede(current_user, 'wells',
    'delete')`.
    """
    # Sin sesión no se puede nada
    if not usuario:
        return False

    # Una acción que no existe es un error de programación, no un permiso
    if accion not in CLAVES_ACCION:
        logger.warning(f"Acción desconocida al comprobar permisos: {accion!r}")
        return False

    permisos = usuario.get("permisos") or {}

    return bool(permisos.get(modulo, NINGUNO).get(accion, False))


# Indicamos si el usuario ve algo del módulo, para decidir si pintarlo en el menú
def ve_algo(usuario: Optional[dict], modulo: str) -> bool:
    """Cierto si puede ver el módulo o alguno de sus submódulos."""
    if not usuario:
        return False

    permisos = usuario.get("permisos") or {}

    # El propio módulo
    if permisos.get(modulo, NINGUNO).get("view"):
        return True

    # O cualquiera que cuelgue de él. Las claves de los hijos llevan el prefijo
    # del padre y un punto, así que basta mirar el nombre.
    prefijo = modulo + "."

    return any(clave.startswith(prefijo) and valores.get("view")
               for clave, valores in permisos.items())
