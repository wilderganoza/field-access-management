"""Modelos del dominio: casos, checklist e historial de solicitudes."""

# Importamos las librerias necesarias
from sqlalchemy import (  # Tipos de columna y restricciones
    BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.orm import relationship  # Relaciones entre modelos

from app.models.base import Base  # Registro declarativo compartido

# Se importan aunque no se citen: `User.role` es un relationship declarado por
# nombre, y SQLAlchemy solo resuelve «Role» si la clase ya esta registrada en el
# mismo mapper. Sin esta linea, la primera consulta sobre `users` falla con
# «failed to locate a name ('Role')» -- y en el login eso salia como credencial
# incorrecta, que es un sintoma que no lleva a ninguna parte.
from app.models.access import Module, Role, RolePermission

# Se citan aqui a proposito. El import es por su efecto -registrar los modelos
# en el mismo mapper, para que `User.role` resuelva «Role»- y un `# noqa` no lo
# protege: pyflakes no lo respeta, asi que el aviso volvia en cada revision.
# Nombrarlos hace que el uso sea real y que quitarlos rompa de verdad.
MODELOS_DE_ACCESO = (Module, Role, RolePermission)


# Guardamos una cuenta de la aplicación.
#
# Antes esto era `user_profiles`: un perfil colgado del uuid de Supabase Auth,
# sin correo ni contraseña, porque de eso se encargaba GoTrue. Al dejar de usar
# Supabase Auth, la identidad vive aquí, y esta tabla tiene la MISMA forma que
# `users` en Field Data Platform.
class User(Base):
    # Nombre de la tabla
    __tablename__ = "users"

    # Identificador autoincremental, como en la app hermana
    id = Column(Integer, primary_key=True)

    # Con qué entra
    username = Column(String(150), nullable=False)
    email = Column(String(255), nullable=False)

    # Hash argon2id. Vacío significa cuenta sin contraseña puesta todavía, que
    # no valida nada: no es lo mismo que «cualquier contraseña vale».
    password_hash = Column(String(255), nullable=False, default="")

    # Quién es
    full_name = Column(String(255), nullable=False, default="")
    department = Column(String(255), nullable=False, default="")
    position = Column(String(255), nullable=False, default="")

    # El perfil, que es quien decide los permisos por módulo
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="SET NULL"))

    # Si la cuenta está habilitada
    is_active = Column(Boolean, nullable=False, default=True)

    # Una cuenta creada o reseteada por un administrador entra con una
    # contraseña ajena: se le exige cambiarla antes de llegar a ningún sitio
    must_change_password = Column(Boolean, nullable=False, default=True)

    # Reseteo de contraseña
    reset_token = Column(String(255), unique=True)
    reset_token_expires = Column(DateTime(timezone=True))

    # Última entrada, para la pantalla de usuarios
    last_login_at = Column(DateTime(timezone=True))

    # Fechas de la fila
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                        onupdate=func.now())

    # El perfil, para leer sus permisos sin una consulta aparte
    role = relationship("Role", lazy="joined")


# Guardamos un caso de validación, que define su propio checklist.
class Case(Base):
    # Nombre de la tabla
    __tablename__ = "cases"

    # Identificador legible, por ejemplo NO_CONDUCTOR
    id = Column(String(100), primary_key=True)

    # Nombre visible del caso
    name = Column(String(255), nullable=False)

    # Icono que lo representa en la interfaz
    icon = Column(String(16), nullable=False, default="📋")

    # Color asociado, en hexadecimal
    color = Column(String(7), nullable=False, default="#4a7cff")

    # Descripción de qué habilita este caso
    description = Column(Text, nullable=False, default="")

    # Si viene de la instalación inicial
    is_default = Column(Boolean, nullable=False, default=False)

    # Fecha de creación
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Preguntas asociadas, ordenadas y borradas junto con el caso
    checklist = relationship(
        "CaseChecklistItem",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="CaseChecklistItem.sort_order",
    )


# Guardamos una pregunta del checklist de un caso.
class CaseChecklistItem(Base):
    # Nombre de la tabla
    __tablename__ = "case_checklist"

    # Identificador autoincremental
    id = Column(Integer, primary_key=True)

    # Caso al que pertenece
    case_id = Column(String(100), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)

    # Texto de la pregunta
    question = Column(Text, nullable=False)

    # Posición dentro del checklist
    sort_order = Column(Integer, nullable=False, default=0)

    # Caso al que pertenece, para navegar en sentido inverso
    case = relationship("Case", back_populates="checklist")


# Guardamos una solicitud ya analizada.
class AnalysisHistory(Base):
    # Nombre de la tabla
    __tablename__ = "analysis_history"

    # Identificador de la solicitud, generado por la aplicación
    id = Column(String(100), primary_key=True)

    # Usuario que la procesó; queda en null si se borra la cuenta
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    # Nombre que le puso el operador
    request_name = Column(String(500), nullable=False, default="")

    # Caso usado, copiado al momento del análisis para que el historial no
    # cambie si después se edita o borra el caso
    case_id = Column(String(100), nullable=False)
    case_name = Column(String(255), nullable=False)
    case_icon = Column(String(16), nullable=False)
    case_color = Column(String(7), nullable=False)

    # Cabeceras del correo de origen
    email_from = Column(Text, nullable=False, default="N/A")
    email_to = Column(Text, nullable=False, default="N/A")
    email_subject = Column(Text, nullable=False, default="Sin asunto")
    email_date = Column(Text, nullable=False, default="N/A")
    email_body = Column(Text, nullable=False, default="")

    # Resumen ejecutivo en markdown
    summary = Column(Text, nullable=False, default="")

    # Veredicto global: APROBADO, RECHAZADO o PENDIENTE
    verdict = Column(String(20), nullable=False, default="PENDIENTE")

    # Momento del análisis
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Archivos analizados
    files = relationship(
        "AnalysisFile", back_populates="analysis", cascade="all, delete-orphan"
    )

    # Resultados del checklist
    results = relationship(
        "AnalysisChecklistResult", back_populates="analysis", cascade="all, delete-orphan"
    )


# Guardamos un archivo incluido en una solicitud.
class AnalysisFile(Base):
    # Nombre de la tabla
    __tablename__ = "analysis_files"

    # Identificador autoincremental
    id = Column(Integer, primary_key=True)

    # Solicitud a la que pertenece
    analysis_id = Column(
        String(100), ForeignKey("analysis_history.id", ondelete="CASCADE"), nullable=False
    )

    # Nombre del archivo
    name = Column(String(500), nullable=False)

    # Extensión o tipo detectado
    file_type = Column(String(50), nullable=False)

    # Si se pudo leer o no, y si ademas quedo conservado
    status = Column(String(20), nullable=False, default="leido")

    # Donde vive el archivo dentro del bucket privado: `{analysis_id}/{nombre}`.
    # Nulo si no se pudo conservar; entonces el historial lo lista pero no
    # ofrece abrirlo, en vez de dar un enlace roto.
    storage_path = Column(Text)

    # Tamano real, para mostrarlo sin ir al bucket
    size_bytes = Column(BigInteger)

    # Huella del contenido: un mismo DNI subido en varias solicitudes se
    # reconoce como el mismo archivo
    content_hash = Column(String(64))

    # Fin del periodo de conservacion. Dos anios desde la subida, o antes si se
    # elimina el caso que lo justificaba.
    retain_until = Column(DateTime(timezone=True))

    # Solicitud a la que pertenece, para navegar en sentido inverso
    analysis = relationship("AnalysisHistory", back_populates="files")


# Guardamos el resultado de una pregunta para una persona o vehículo.
class AnalysisChecklistResult(Base):
    # Nombre de la tabla
    __tablename__ = "analysis_checklist_results"

    # Identificador autoincremental
    id = Column(Integer, primary_key=True)

    # Solicitud a la que pertenece
    analysis_id = Column(
        String(100), ForeignKey("analysis_history.id", ondelete="CASCADE"), nullable=False
    )

    # Persona o vehículo evaluado
    person_name = Column(String(500), nullable=False, default="")

    # Pregunta evaluada
    question = Column(Text, nullable=False)

    # Resultado: APROBADO, RECHAZADO o PENDIENTE
    result = Column(String(20), nullable=False, default="PENDIENTE")

    # Justificación con datos concretos
    explanation = Column(Text, nullable=False, default="")

    # Solicitud a la que pertenece, para navegar en sentido inverso
    analysis = relationship("AnalysisHistory", back_populates="results")


# Guardamos una plantilla de prompt editable desde la interfaz.
class PromptTemplate(Base):
    # Nombre de la tabla
    __tablename__ = "prompt_templates"

    # Identificador de la plantilla
    id = Column(String(100), primary_key=True)

    # Contenido con marcadores {{VARIABLE}}
    content = Column(Text, nullable=False)

    # Última edición
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# Configuración global editable por administradores. Los valores sensibles se
# cifran antes de llegar a esta tabla; nunca se devuelven completos al cliente.
class GlobalSetting(Base):
    __tablename__ = "global_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False, default="")
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )
