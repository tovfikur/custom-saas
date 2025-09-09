# app/api/v1/deployments.py
from typing import Any, Dict, List, Literal, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.admin import Admin
from app.services.odoo_deployment_service import OdooDeploymentService
from app.api.v1.auth import get_current_active_admin


router = APIRouter(prefix="/deployments", tags=["deployments"])


class PopupAction(BaseModel):
    id: Literal["confirm", "cancel"] = "confirm"
    label: str = "Confirm"
    style: Literal["primary", "danger", "secondary"] = "primary"

class PopupRequest(BaseModel):
    kind: Literal["confirm", "info", "warning", "danger"] = "confirm"
    title: str
    message: str
    confirm_label: str = "Confirm"
    cancel_label: str = "Cancel"
    # place any payload you want to pass back when the user clicks "confirm"
    context: Dict[str, Any] = Field(default_factory=dict)

class PopupResponse(BaseModel):
    modal_id: str
    issued_at: datetime
    kind: Literal["confirm", "info", "warning", "danger"]
    title: str
    message: str
    actions: List[PopupAction]
    context: Dict[str, Any]

@router.post("/popup", response_model=PopupResponse, status_code=201)
async def build_popup(
    req: PopupRequest,
    _: Admin = Depends(get_current_active_admin),
):
    modal_id = "mdl_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return PopupResponse(
        modal_id=modal_id,
        issued_at=datetime.now(timezone.utc),
        kind=req.kind,
        title=req.title,
        message=req.message,
        actions=[
            PopupAction(id="confirm", label=req.confirm_label, style="danger" if req.kind == "danger" else "primary"),
            PopupAction(id="cancel", label=req.cancel_label, style="secondary"),
        ],
        context=req.context,
    )

class PopupDecision(BaseModel):
    modal_id: str
    decision: Literal["confirm", "cancel"]
    context: Dict[str, Any] = Field(default_factory=dict)

@router.post("/popup/decision")
async def popup_decision(
    decision: PopupDecision,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin),
):

    if decision.decision == "cancel":
        return {"success": True, "modal_id": decision.modal_id, "decision": "cancel"}

    ctx_type = decision.context.get("type")
    if ctx_type != "odoo_deploy":
        # Nothing to do server-side
        return {"success": True, "modal_id": decision.modal_id, "decision": decision.decision}

    payload = decision.context.get("payload") or {}
    required = ["template_id", "vps_id", "deployment_name", "domain"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing fields in payload: {', '.join(missing)}")

    svc = OdooDeploymentService(db)
    deployment = await svc.deploy_odoo(
        template_id=payload["template_id"],
        vps_id=payload["vps_id"],
        deployment_name=payload["deployment_name"],
        domain=payload["domain"],
        admin_id=str(current_admin.id),
        selected_version=payload.get("selected_version"),
        selected_modules=payload.get("selected_modules"),
        custom_config=payload.get("custom_config"),
        custom_env_vars=payload.get("custom_env_vars"),
        admin_password=payload.get("admin_password"),
    )

    if not deployment or deployment.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=getattr(deployment, "error_message", "Deployment failed"),
        )

    return {
        "success": True,
        "modal_id": decision.modal_id,
        "decision": decision.decision,
        "deployment_id": str(deployment.id),
        "status": deployment.status,
    }

class DeployOdooRequest(BaseModel):
    template_id: str
    vps_id: str
    deployment_name: str
    domain: str
    selected_version: Optional[str] = None
    selected_modules: Optional[List[str]] = None
    custom_config: Optional[Dict[str, Any]] = None
    custom_env_vars: Optional[Dict[str, Any]] = None
    admin_password: Optional[str] = None  # optional override

class DeployOdooResponse(BaseModel):
    success: bool
    deployment_id: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None

@router.post("/odoo", response_model=DeployOdooResponse, status_code=201)
async def deploy_odoo(
    body: DeployOdooRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin),
):
    svc = OdooDeploymentService(db)

    deployment = await svc.deploy_odoo(
        template_id=body.template_id,
        vps_id=body.vps_id,
        deployment_name=body.deployment_name,
        domain=body.domain,
        admin_id=str(current_admin.id),
        selected_version=body.selected_version,
        selected_modules=body.selected_modules,
        custom_config=body.custom_config,
        custom_env_vars=body.custom_env_vars,
        admin_password=body.admin_password,
    )

    if not deployment:
        raise HTTPException(status_code=500, detail="Deployment could not be created")

    if deployment.status == "failed":
        msg = deployment.error_message or "Deployment failed"
        return DeployOdooResponse(success=False, deployment_id=str(deployment.id), status=deployment.status, message=msg)

    return DeployOdooResponse(success=True, deployment_id=str(deployment.id), status=deployment.status)
