"""Perfiles y permisos por módulo.

Un perfil es un conjunto de permisos con nombre. Para cada módulo y submódulo se
indica qué puede hacer: ver, crear, editar, eliminar y descargar.

La matriz se guarda entera en cada guardado —se borra y se reinserta— en vez de
ir marcando diferencias. Son como mucho 55 filas por perfil, y hacerlo así evita
el estado intermedio en el que un permiso se quitó y el siguiente todavía no se
puso.

Es la misma pantalla que en Verificación de Permisos: aplicaciones hermanas,
misma forma de administrar los permisos.
"""

# Importamos las librerias necesarias
from typing import Dict, List  # Tipos

from fastapi import APIRouter, Depends, Form, Request  # Router y formularios
from fastapi.responses import HTMLResponse, Response  # Respuestas
from sqlalchemy.orm import Session  # Sesión de base de datos
from starlette.datastructures import FormData  # Formulario ya leído

from app.core.deps import exige, formulario_enviado  # Permiso y formulario
from app.core.logging import get_logger  # Para registrar la actividad
from app.db.session import get_db  # Dependencia de sesión
from app.models.access import ACCIONES, Module, Role, RolePermission  # Catálogo
from app.models.analysis import User  # Para saber si el perfil está en uso
from app.web.templating import page_context, templates, toast_header  # Plantillas

# Creamos el logger de este módulo
logger = get_logger(__name__)

# Creamos el router
router = APIRouter(prefix="/admin/roles")


# Ordenamos el árbol de módulos como se ve en el menú
def _arbol(db: Session) -> List[Module]:
    """Los módulos con sus hijos detrás de cada padre."""
    modulos = db.query(Module).filter(Module.is_active).all()

    # Se indexan los hijos por padre para no consultar dentro del bucle
    hijos: Dict[int, List[Module]] = {}

    for m in modulos:
        if m.parent_id:
            hijos.setdefault(m.parent_id, []).append(m)

    ordenado: List[Module] = []

    for padre in sorted((m for m in modulos if not m.parent_id),
                        key=lambda m: (m.sort_order, m.name)):
        ordenado.append(padre)
        ordenado.extend(sorted(hijos.get(padre.id, []),
                               key=lambda m: (m.sort_order, m.name)))

    return ordenado


# Componemos el contexto de la pantalla
def _contexto(request: Request, current_user: dict, db: Session, **extra):
    perfiles = db.query(Role).order_by(Role.is_system.desc(), Role.name).all()

    # Cuántas cuentas usa cada perfil, para avisar antes de borrarlo
    uso = {r.id: db.query(User).filter(User.role_id == r.id).count() for r in perfiles}

    return page_context(request, current_user=current_user, roles=perfiles,
                        uso=uso, modules=_arbol(db), acciones=ACCIONES, **extra)


# Devolvemos un error dentro del fragmento
def _error(request: Request, current_user: dict, mensaje: str, status_code: int = 400):
    return templates.TemplateResponse(
        "partials/error_message.html",
        page_context(request, current_user=current_user, message=mensaje),
        status_code=status_code,
    )


# Mostramos el listado de perfiles
@router.get("", response_class=HTMLResponse)
def listar(request: Request,
           current_user: dict = Depends(exige("admin/roles", "view")),
           db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "pages/roles.html", _contexto(request, current_user, db))


# Mostramos la matriz de un perfil
@router.get("/{role_id}", response_class=HTMLResponse)
def detalle(role_id: int, request: Request,
            current_user: dict = Depends(exige("admin/roles", "view")),
            db: Session = Depends(get_db)):
    perfil = db.query(Role).filter(Role.id == role_id).first()

    if perfil is None:
        return _error(request, current_user, "Ese perfil ya no existe.", 404)

    # Lo concedido hoy, por módulo, para marcar las casillas
    concedido = {
        p.module_id: p
        for p in db.query(RolePermission).filter(RolePermission.role_id == role_id).all()
    }

    return templates.TemplateResponse(
        "pages/role_detail.html",
        _contexto(request, current_user, db, role=perfil, concedido=concedido),
    )


# Creamos un perfil
@router.post("", response_class=HTMLResponse)
def crear(
    request: Request,
    key: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    current_user: dict = Depends(exige("admin/roles", "create")),
    db: Session = Depends(get_db),
):
    clave = (key or "").strip().lower().replace(" ", "-")

    if not clave or not name.strip():
        return _error(request, current_user, "La clave y el nombre son obligatorios.")

    if db.query(Role).filter(Role.key == clave).first():
        return _error(request, current_user, f"Ya existe un perfil con la clave «{clave}».")

    perfil = Role(key=clave, name=name.strip(), description=(description or "").strip())

    try:
        db.add(perfil)
        db.commit()

    except Exception as exc:
        db.rollback()
        logger.warning(f"No se pudo crear el perfil {clave}: {exc}")

        return _error(request, current_user,
                      "No se pudo crear: la base de datos rechazó los datos.", 409)

    logger.info(f"Perfil {clave} creado por {current_user['email']}")

    respuesta = templates.TemplateResponse(
        "partials/roles_table.html", _contexto(request, current_user, db), status_code=201)
    respuesta.headers["HX-Trigger"] = toast_header("Perfil creado")

    return respuesta


# Guardamos la matriz completa de un perfil
@router.post("/{role_id}", response_class=HTMLResponse)
def guardar(
    role_id: int,
    request: Request,
    form: FormData = Depends(formulario_enviado),
    current_user: dict = Depends(exige("admin/roles", "edit")),
    db: Session = Depends(get_db),
):
    perfil = db.query(Role).filter(Role.id == role_id).first()

    if perfil is None:
        return _error(request, current_user, "Ese perfil ya no existe.", 404)

    # Los datos del perfil, si vinieron en el mismo formulario
    if form.get("name"):
        perfil.name = str(form.get("name")).strip()

    perfil.description = str(form.get("description") or "").strip()

    # Las casillas llegan como `perm-<module_id>-<accion>`. Solo llegan las
    # marcadas: HTML no envía las casillas sin marcar, así que lo que no venga
    # es un permiso quitado.
    modulos = db.query(Module).all()

    filas = []

    for modulo in modulos:
        valores = {
            columna: form.get(f"perm-{modulo.id}-{clave}") is not None
            for clave, _, columna in ACCIONES
        }

        # Un módulo sin ninguna acción marcada no genera fila: así el mapa de
        # permisos distingue «no concedido» de «concedido en falso», y la
        # herencia del padre puede seguir aplicando
        if not any(valores.values()):
            continue

        filas.append(RolePermission(role_id=role_id, module_id=modulo.id, **valores))

    try:
        # Se reemplaza la matriz entera: más simple que calcular diferencias, y
        # sin estado intermedio a medio guardar
        (db.query(RolePermission)
           .filter(RolePermission.role_id == role_id)
           .delete(synchronize_session=False))

        db.add_all(filas)
        db.commit()

    except Exception as exc:
        db.rollback()
        logger.warning(f"No se pudieron guardar los permisos de {role_id}: {exc}")

        return _error(request, current_user,
                      "No se pudo guardar: la base de datos rechazó los datos.", 409)

    logger.info(f"Permisos del perfil {perfil.key} guardados por {current_user['email']} "
                f"({len(filas)} módulo(s) con acceso)")

    respuesta = templates.TemplateResponse(
        "partials/roles_table.html", _contexto(request, current_user, db))
    respuesta.headers["HX-Trigger"] = toast_header(
        f"Permisos guardados: {len(filas)} módulo(s) con acceso")

    return respuesta


# Eliminamos un perfil
@router.delete("/{role_id}", response_class=HTMLResponse)
def eliminar(role_id: int, request: Request,
             current_user: dict = Depends(exige("admin/roles", "delete")),
             db: Session = Depends(get_db)):
    perfil = db.query(Role).filter(Role.id == role_id).first()

    if perfil is None:
        return Response(status_code=404)

    # Un perfil de sistema no se borra: sin `admin` nadie podría administrar
    if perfil.is_system:
        return _error(request, current_user,
                      f"«{perfil.name}» es un perfil de sistema y no se puede eliminar.")

    # Y uno en uso dejaría cuentas sin permisos de golpe
    en_uso = db.query(User).filter(User.role_id == role_id).count()

    if en_uso:
        return _error(request, current_user,
                      f"«{perfil.name}» está asignado a {en_uso} cuenta(s). "
                      "Cámbiales el perfil antes de eliminarlo.", 409)

    clave = perfil.key

    # Se comprobo que no es de sistema y que nadie lo usa, pero entre esa
    # comprobacion y este borrado alguien puede haberlo asignado
    try:
        db.delete(perfil)
        db.commit()

    except Exception as exc:
        db.rollback()
        logger.warning(f"No se pudo eliminar el perfil {clave}: {exc}")

        return _error(request, current_user,
                      "No se pudo eliminar: puede que alguien lo tenga asignado.", 409)

    logger.info(f"Perfil {clave} eliminado por {current_user['email']}")

    respuesta = templates.TemplateResponse(
        "partials/roles_table.html", _contexto(request, current_user, db))
    respuesta.headers["HX-Trigger"] = toast_header("Perfil eliminado")

    return respuesta
