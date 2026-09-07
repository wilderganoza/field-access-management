"""Perfiles y permisos por módulo.

Tres tablas con la misma forma en las dos aplicaciones:

    modules            el árbol de módulos y submódulos del menú
    roles              el perfil: un conjunto de permisos con nombre
    role_permissions   la matriz, con las cinco acciones

Un submódulo hereda del padre: si el perfil no tiene fila propia para
«Assets > Wells» pero sí para «Assets», vale la del padre. Así se puede dar
acceso grueso sin enumerar los treinta y cuatro submódulos de FDP.

`modules.table_name` es lo que permite que una política RLS sepa qué módulo
gobierna cada tabla. Sin esa columna habría que escribir las políticas a mano,
tabla por tabla, y mantenerlas sincronizadas para siempre.

Este archivo es el mismo en Field Data Platform y en Verificación de Permisos.
"""

# Importamos las librerias necesarias
from sqlalchemy import (  # Tipos de columna y restricciones
    Boolean, Column, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.orm import relationship  # Para navegar entre perfil y permisos
from sqlalchemy.types import DateTime  # Marca de tiempo con zona

from app.models.base import Base  # Registro declarativo compartido


# Un nodo del menú: un módulo, o un submódulo si tiene padre
class Module(Base):
    # Nombre de la tabla
    __tablename__ = "modules"

    # Identificador autoincremental
    id = Column(Integer, primary_key=True)

    # Clave estable con la que el código pregunta por el permiso. No cambia
    # aunque se renombre la pantalla: `puede('well-test', 'crear')`.
    key = Column(String(100), nullable=False, unique=True)

    # Lo que se lee en el menú y en la pantalla de perfiles
    name = Column(String(150), nullable=False)

    # El módulo del que cuelga, o nulo si es de primer nivel
    parent_id = Column(Integer, ForeignKey("modules.id", ondelete="CASCADE"))

    # La tabla que gobierna este módulo, cuando gobierna alguna. Es lo que ata
    # el permiso con la política RLS.
    table_name = Column(String(100))

    # Orden dentro de su nivel
    sort_order = Column(Integer, nullable=False, default=0)

    # Un módulo retirado deja de ofrecerse sin borrar los permisos que lo citan
    is_active = Column(Boolean, nullable=False, default=True)

    # Los hijos, para pintar el árbol de una vez
    children = relationship(
        "Module", backref="parent", remote_side=[id], viewonly=True,
    )


# Un perfil: el conjunto de permisos que se asigna a una persona
class Role(Base):
    # Nombre de la tabla
    __tablename__ = "roles"

    # Identificador autoincremental
    id = Column(Integer, primary_key=True)

    # Clave estable, la que usa el código
    key = Column(String(50), nullable=False, unique=True)

    # Lo que se lee en pantalla
    name = Column(String(100), nullable=False)

    # Para qué sirve este perfil, en una frase
    description = Column(Text, nullable=False, default="")

    # Un perfil de sistema no se puede borrar desde la pantalla: si se pudiera,
    # alguien se quedaría sin forma de administrar la aplicación
    is_system = Column(Boolean, nullable=False, default=False)

    # Cuándo se creó
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Sus permisos, que se borran con él
    permissions = relationship(
        "RolePermission", back_populates="role",
        cascade="all, delete-orphan", passive_deletes=True,
    )


# Lo que un perfil puede hacer en un módulo
class RolePermission(Base):
    # Nombre de la tabla
    __tablename__ = "role_permissions"

    # La clave es el par, no un identificador propio: un perfil tiene como
    # mucho una fila por módulo
    role_id = Column(
        Integer, ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True, nullable=False,
    )
    module_id = Column(
        Integer, ForeignKey("modules.id", ondelete="CASCADE"),
        primary_key=True, nullable=False,
    )

    # Las cinco acciones
    can_view = Column(Boolean, nullable=False, default=False)
    can_create = Column(Boolean, nullable=False, default=False)
    can_edit = Column(Boolean, nullable=False, default=False)
    can_delete = Column(Boolean, nullable=False, default=False)
    can_download = Column(Boolean, nullable=False, default=False)

    # Para navegar desde el permiso a su perfil y a su módulo
    role = relationship("Role", back_populates="permissions")
    module = relationship("Module")


# Las acciones, en el orden en que se muestran. Se declaran una sola vez para
# que la pantalla, el decorador de rutas y las políticas no puedan discrepar.
ACCIONES = (
    ("view", "Ver", "can_view"),
    ("create", "Crear", "can_create"),
    ("edit", "Editar", "can_edit"),
    ("delete", "Eliminar", "can_delete"),
    ("download", "Descargar", "can_download"),
)

# La columna que corresponde a cada acción, para resolver sin encadenar ifs
COLUMNA_DE_ACCION = {clave: columna for clave, _, columna in ACCIONES}
