from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, require_global, require_permission
from app.database import get_db
from app.models import SystemSetting
from app.schemas import SystemSettingResponse, SystemSettingUpdate
from app.services.system_settings import SESSION_LIFETIME_KEY, validate_session_minutes
from app.release import build_metadata
from app.services.updates import UpdateStatus, checker

router = APIRouter(prefix="/system-settings", tags=["system settings"])


@router.get("/updates", response_model=UpdateStatus)
async def update_status(principal: Principal = Depends(require_permission("system_settings.manage"))):
    require_global(principal, "system_settings.manage")
    return await checker.status()


@router.post("/updates/check", response_model=UpdateStatus)
async def check_updates(principal: Principal = Depends(require_permission("system_settings.manage"))):
    require_global(principal, "system_settings.manage")
    return await checker.status(refresh=True)


@router.get("/build-info")
def installation_info(principal: Principal = Depends(require_permission("system_settings.manage"))):
    require_global(principal, "system_settings.manage")
    return build_metadata()


def _response(setting: SystemSetting) -> SystemSettingResponse:
    return SystemSettingResponse.model_validate(
        {
            "id": setting.id,
            "key": setting.key,
            "value_": "[redacted]" if setting.sensitive else setting.value_,
            "description": setting.description,
            "sensitive": setting.sensitive,
            "updated_at": setting.updated_at,
        }
    )


@router.get("", response_model=list[SystemSettingResponse])
def list_system_settings(
    principal: Principal = Depends(require_permission("system_settings.manage")),
    db: Session = Depends(get_db),
):
    require_global(principal, "system_settings.manage")
    return [_response(item) for item in db.scalars(select(SystemSetting).order_by(SystemSetting.key))]


@router.patch("/{key}", response_model=SystemSettingResponse)
def update_system_setting(
    key: str,
    payload: SystemSettingUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("system_settings.manage")),
    db: Session = Depends(get_db),
):
    require_global(principal, "system_settings.manage")
    if key in {"auth.restore_epoch", "connector_local_release_instance"} or key.startswith("connector_local_release_restoration:"):
        raise HTTPException(status_code=409, detail="This protected internal setting cannot be edited through the application")
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if setting is None:
        raise HTTPException(status_code=404, detail="System setting not found")
    if key == SESSION_LIFETIME_KEY:
        try:
            validate_session_minutes(payload.value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    setting.value_ = payload.value
    setting.updated_by_user_id = principal.user.id
    add_audit_event(
        db,
        action="system_setting.updated",
        target_type="system_setting",
        target_id=setting.id,
        actor=principal.user,
        summary=f"System setting {setting.key} updated",
        metadata={"key": setting.key, "sensitive": setting.sensitive},
        request=request,
    )
    db.commit()
    db.refresh(setting)
    return _response(setting)
