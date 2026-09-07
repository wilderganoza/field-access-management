"""Gestión de cuentas.

Las cuentas viven en `users`, en el esquema de esta aplicación. Antes vivían en
Supabase Auth y aquí solo quedaba un perfil de organización; ahora la identidad
es nuestra y esta pantalla es donde se administra por completo: alta, baja,
datos, perfil de permisos y reseteo de contraseña.

Es la misma pantalla que en Verificación de Permisos: son aplicaciones hermanas
y una cuenta se gestiona igual en las dos.
"""

# Importamos las librerias necesarias
import secrets  # Para la contraseña inicial que entrega el administrador
import string  # Alfabeto de esa contraseña

from fastapi import APIRouter, Depends, Form, Request  # Router y formularios
from fastapi.responses import HTMLResponse, Response  # Respuestas
from sqlalchemy import func  # Para comparar sin distinguir mayúsculas
from sqlalchemy.orm import Session  # Sesión de base de datos

from app.core.deps import exige  # Exige el permiso del perfil sobre el módulo
from app.core.logging import get_logger  # Para registrar la actividad
from app.core.security import hash_password  # Hash de la contraseña
from app.db.session import get_db  # Dependencia de sesión
from app.models.access import Role  # Perfiles de permisos
from app.models.analysis import User  # La cuenta
from app.web.templating import page_context, templates, toast_header  # Plantillas

# Creamos el logger de este módulo
logger = get_logger(__name__)

# Creamos el router
router = APIRouter(prefix="/users")

# El mínimo que se exige a una contraseña
MIN_PASSWORD = 8

# Longitud de la contraseña que se genera al crear una cuenta
LARGO_GENERADA = 14


# Generamos una contraseña inicial legible pero no adivinable
def _contrasena_inicial() -> str:
    """Una contraseña aleatoria para entregar al dueño de la cuenta.

    Se generan aquí y no las escribe el administrador a propósito: una
    contraseña elegida por otra persona tiende a ser la misma para todos. Se
    entrega una vez, y el dueño está obligado a cambiarla al entrar.
    """
    # Sin caracteres que se confundan al dictarla: 0/O, 1/l/I
    alfabeto = "".join(c for c in string.ascii_letters + string.digits
                       if c not in "0O1lI")

    return "".join(secrets.choice(alfabeto) for _ in range(LARGO_GENERADA))


# Componemos el contexto de la pantalla
def _contexto(request: Request, current_user: dict, db: Session, **extra):
    # Las cuentas, la más reciente primero
    usuarios = db.query(User).order_by(User.created_at.desc()).all()

    # Y los perfiles disponibles para el desplegable
    perfiles = db.query(Role).order_by(Role.name).all()

    return page_context(request, current_user=current_user, users=usuarios,
                        roles=perfiles, min_password=MIN_PASSWORD, **extra)


# Devolvemos solo la tabla, que es lo que HTMX reemplaza
def _tabla(request: Request, current_user: dict, db: Session, status_code: int = 200):
    return templates.TemplateResponse(
        "partials/users_table.html",
        _contexto(request, current_user, db),
        status_code=status_code,
    )


# Devolvemos un error dentro del fragmento, sin recargar la pantalla
def _error(request: Request, current_user: dict, mensaje: str, status_code: int = 400):
    return templates.TemplateResponse(
        "partials/error_message.html",
        page_context(request, current_user=current_user, message=mensaje),
        status_code=status_code,
    )


# Mostramos la pantalla de administración de cuentas
@router.get("", response_class=HTMLResponse)
def listar(request: Request,
           current_user: dict = Depends(exige("admin/users", "view")),
           db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "pages/users.html", _contexto(request, current_user, db))


# Creamos una cuenta
@router.post("", response_class=HTMLResponse)
def crear(
    request: Request,
    email: str = Form(...),
    username: str = Form(""),
    full_name: str = Form(""),
    department: str = Form(""),
    position: str = Form(""),
    role_id: str = Form(""),
    current_user: dict = Depends(exige("admin/users", "create")),
    db: Session = Depends(get_db),
):
    correo = (email or "").strip().lower()

    # Sin correo no hay con qué entrar
    if not correo:
        return _error(request, current_user, "El correo es obligatorio.")

    # El usuario, si no se indica, sale del correo
    usuario = (username or correo.split("@")[0]).strip()

    # La base lo impide igualmente, pero decirlo aquí da un mensaje útil en vez
    # de un error de restricción
    if db.query(User).filter(func.lower(User.email) == correo).first():
        return _error(request, current_user, f"Ya hay una cuenta con el correo «{correo}».")

    if db.query(User).filter(func.lower(User.username) == usuario.lower()).first():
        return _error(request, current_user, f"Ya hay una cuenta con el usuario «{usuario}».")

    # El perfil debe existir; sin perfil la cuenta no puede hacer nada
    perfil = db.query(Role).filter(Role.id == int(role_id)).first() if role_id.isdigit() else None

    if perfil is None:
        return _error(request, current_user, "Elige un perfil para la cuenta.")

    # La contraseña la genera el servidor y se entrega una sola vez
    inicial = _contrasena_inicial()

    fila = User(
        username=usuario,
        email=correo,
        password_hash=hash_password(inicial),
        full_name=(full_name or "").strip(),
        department=(department or "").strip(),
        position=(position or "").strip(),
        role_id=perfil.id,
        is_active=True,
        # La puso un administrador: el dueño tiene que cambiarla al entrar
        must_change_password=True,
    )

    try:
        db.add(fila)
        db.commit()

    # Lo que rechace la base se explica, no se convierte en un 500
    except Exception as exc:
        db.rollback()
        logger.warning(f"No se pudo crear la cuenta {correo}: {exc}")

        return _error(request, current_user,
                      "No se pudo crear la cuenta: la base de datos rechazó los datos.", 409)

    logger.info(f"Cuenta {correo} creada por {current_user['email']}")

    respuesta = _tabla(request, current_user, db, status_code=201)

    # La contraseña se enseña UNA vez, en el aviso. No se guarda en claro ni se
    # vuelve a poder consultar: si se pierde, se resetea.
    respuesta.headers["HX-Trigger"] = toast_header(
        f"Cuenta creada. Contraseña inicial: {inicial}")

    return respuesta


# Actualizamos una cuenta
@router.post("/{user_id}", response_class=HTMLResponse)
def actualizar(
    user_id: int,
    request: Request,
    full_name: str = Form(""),
    department: str = Form(""),
    position: str = Form(""),
    role_id: str = Form(""),
    is_active: str = Form(""),
    reset_password: str = Form(""),
    current_user: dict = Depends(exige("admin/users", "edit")),
    db: Session = Depends(get_db),
):
    fila = db.query(User).filter(User.id == user_id).first()

    if fila is None:
        return _error(request, current_user, "Esa cuenta ya no existe.", 404)

    activa = is_active == "on"

    # Un administrador no puede quitarse a sí mismo el acceso: si lo hiciera,
    # nadie podría devolvérselo desde la aplicación
    if fila.id == current_user["id"]:
        if not activa:
            return _error(request, current_user, "No puedes desactivar tu propia cuenta.")

        if role_id.isdigit() and int(role_id) != fila.role_id:
            nuevo = db.query(Role).filter(Role.id == int(role_id)).first()

            if nuevo is None or nuevo.key != "admin":
                return _error(request, current_user,
                              "No puedes quitarte a ti mismo el perfil de administrador.")

    fila.full_name = (full_name or "").strip()
    fila.department = (department or "").strip()
    fila.position = (position or "").strip()
    fila.is_active = activa

    if role_id.isdigit():
        fila.role_id = int(role_id)

    mensaje = "Cuenta actualizada"

    # El reseteo entrega una contraseña nueva y vuelve a exigir el cambio
    if reset_password == "on":
        inicial = _contrasena_inicial()
        fila.password_hash = hash_password(inicial)
        fila.must_change_password = True
        mensaje = f"Contraseña restablecida: {inicial}"

    try:
        db.commit()

    except Exception as exc:
        db.rollback()
        logger.warning(f"No se pudo actualizar la cuenta {user_id}: {exc}")

        return _error(request, current_user,
                      "No se pudo guardar: la base de datos rechazó los datos.", 409)

    logger.info(f"Cuenta {fila.email} actualizada por {current_user['email']}")

    respuesta = _tabla(request, current_user, db)
    respuesta.headers["HX-Trigger"] = toast_header(mensaje)

    return respuesta


# Eliminamos una cuenta
@router.delete("/{user_id}", response_class=HTMLResponse)
def eliminar(
    user_id: int,
    request: Request,
    current_user: dict = Depends(exige("admin/users", "delete")),
    db: Session = Depends(get_db),
):
    fila = db.query(User).filter(User.id == user_id).first()

    if fila is None:
        return Response(status_code=404)

    # Borrarse a uno mismo deja la aplicación sin quien la administre
    if fila.id == current_user["id"]:
        return _error(request, current_user, "No puedes eliminar tu propia cuenta.")

    correo = fila.email

    # Auditoría y sesiones referencian la cuenta, así que la base puede
    # impedirlo. Se dice, en vez de fallar con un 500.
    try:
        db.delete(fila)
        db.commit()

    except Exception as exc:
        db.rollback()
        logger.warning(f"No se pudo eliminar la cuenta {user_id}: {exc}")

        return _error(
            request, current_user,
            "No se puede eliminar: hay registros que dependen de esta cuenta. "
            "Desactívala en vez de borrarla.", 409)

    logger.info(f"Cuenta {correo} eliminada por {current_user['email']}")

    respuesta = _tabla(request, current_user, db)
    respuesta.headers["HX-Trigger"] = toast_header("Cuenta eliminada")

    return respuesta
