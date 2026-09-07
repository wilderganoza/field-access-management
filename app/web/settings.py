"""Configuración administrativa del proveedor de IA."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.deps import exige_tabla
from app.core.errores import motivo_de_base
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.analysis import GlobalSetting
from app.services.openai_config import (
    IA_MODEL_SETTING, MODELOS_IA, MODELOS_IA_IDS, OPENAI_KEY_SETTING,
    obtener_clave_openai, obtener_modelo_ia, origen_clave_openai,
)
from app.services.secretos import cifrar
from app.web.templating import page_context, templates, toast_header


router = APIRouter(prefix="/settings")
logger = get_logger(__name__)


def _contexto(request, current_user, db, error=None):
    origen = origen_clave_openai(db)
    return page_context(
        request,
        current_user=current_user,
        configured=bool(obtener_clave_openai(db)),
        source=origen,
        models=MODELOS_IA,
        selected_model=obtener_modelo_ia(db),
        error=error,
    )


@router.get("", response_class=HTMLResponse)
def settings_page(
    request: Request,
    current_user: dict = Depends(exige_tabla("global_settings", "view")),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        "pages/settings.html", _contexto(request, current_user, db)
    )


@router.post("/openai", response_class=HTMLResponse)
def save_openai_key(
    request: Request,
    api_key: str = Form(""),
    model: str = Form(...),
    current_user: dict = Depends(exige_tabla("global_settings", "edit")),
    db: Session = Depends(get_db),
):
    nueva = api_key.strip()
    actual = obtener_clave_openai(db)

    if not nueva and not actual:
        return templates.TemplateResponse(
            "partials/settings_panel.html",
            _contexto(request, current_user, db, "Ingresa una API key de IA."),
            status_code=400,
        )

    if nueva and (len(nueva) < 20 or any(c.isspace() for c in nueva)):
        return templates.TemplateResponse(
            "partials/settings_panel.html",
            _contexto(request, current_user, db, "La API key no tiene un formato válido."),
            status_code=400,
        )

    if model not in MODELOS_IA_IDS:
        return templates.TemplateResponse(
            "partials/settings_panel.html",
            _contexto(request, current_user, db, "Selecciona un modelo de IA válido."),
            status_code=400,
        )

    if nueva:
        fila = db.query(GlobalSetting).filter(
            GlobalSetting.key == OPENAI_KEY_SETTING
        ).first()

        if fila is None:
            fila = GlobalSetting(key=OPENAI_KEY_SETTING, value=cifrar(nueva))
            db.add(fila)
        else:
            fila.value = cifrar(nueva)

    fila_modelo = db.query(GlobalSetting).filter(
        GlobalSetting.key == IA_MODEL_SETTING
    ).first()
    if fila_modelo is None:
        db.add(GlobalSetting(key=IA_MODEL_SETTING, value=model))
    else:
        fila_modelo.value = model

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning(
            "No se pudo guardar la configuración de IA: %s", type(exc).__name__
        )
        return templates.TemplateResponse(
            "partials/settings_panel.html",
            _contexto(
                request, current_user, db,
                motivo_de_base(exc, "configuración de IA"),
            ),
            status_code=409,
        )

    if nueva:
        logger.info(
            "Credencial de IA actualizada desde Configuración por %s",
            current_user["email"],
        )

    logger.info(
        "Modelo de IA actualizado a %s por %s", model, current_user["email"]
    )

    response = templates.TemplateResponse(
        "partials/settings_panel.html", _contexto(request, current_user, db)
    )
    response.headers["HX-Trigger"] = toast_header(
        "Configuración de IA guardada", "success"
    )
    return response
