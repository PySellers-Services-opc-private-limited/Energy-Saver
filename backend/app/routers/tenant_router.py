"""Tenants CRUD router — full tenant management with buildings & subscriptions."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.tenant_model import Tenant
from app.models.building_model import Building
from app.models.subscription_model import Subscription
from app.models.device_model import Device
from app.models.energy_log_model import EnergyLog
from app.models.alert_model import TenantAlert
from app.schemas import (
    BuildingCreate,
    BuildingResponse,
    BuildingUpdate,
    SubscriptionCreate,
    SubscriptionResponse,
    TenantCreate,
    TenantResponse,
    TenantUpdate,
    DeviceResponse,
)
from app.utils.jwt_utils import get_current_user_payload, require_admin, get_unit_key_or_none

router = APIRouter(prefix="/tenants", tags=["Tenants"])

PLAN_DEFAULTS = {
    "basic":      {"max_devices": 5,  "max_users": 2,  "max_buildings": 1,  "price": 499},
    "pro":        {"max_devices": 25, "max_users": 10, "max_buildings": 5,  "price": 1999},
    "enterprise": {"max_devices": 9999, "max_users": 9999, "max_buildings": 9999, "price": 7999},
}


# ── DB dependency ─────────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
#  TENANT CRUD
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/", response_model=list[TenantResponse], summary="List tenants")
def get_tenants(
    db: Session = Depends(get_db),
    unit_key: str | None = Depends(get_unit_key_or_none),
) -> list[Tenant]:
    q = db.query(Tenant).order_by(Tenant.created_at.desc())
    if unit_key:
        q = q.filter(Tenant.unit_key == unit_key)
    return q.all()


@router.get("/my-unit", summary="Get the current tenant user's own unit detail")
def get_my_unit(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    """Return the full tenant detail for the logged-in tenant user's unit_key."""
    uk = payload.get("unit_key", "")
    if not uk:
        raise HTTPException(status_code=404, detail="No unit_key linked to this account")
    tenant = db.query(Tenant).filter(Tenant.unit_key == uk).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant unit not found")

    devices = db.query(Device).filter(Device.unit_key == tenant.unit_key).all()
    total_kwh = (
        db.query(func.sum(EnergyLog.consumption))
        .filter(EnergyLog.unit_key == tenant.unit_key)
        .scalar()
    ) or 0
    alert_count = (
        db.query(func.count(TenantAlert.id))
        .filter(TenantAlert.unit_key == tenant.unit_key)
        .scalar()
    ) or 0
    buildings = db.query(Building).filter(Building.tenant_id == tenant.id, Building.is_active == True).all()
    subscription = (
        db.query(Subscription)
        .filter(Subscription.tenant_id == tenant.id, Subscription.status == "active")
        .first()
    )
    plan_info = PLAN_DEFAULTS.get(tenant.subscription_plan or "basic", PLAN_DEFAULTS["basic"])

    return {
        "tenant": TenantResponse.model_validate(tenant).model_dump(),
        "device_count": len(devices),
        "device_limit": plan_info["max_devices"],
        "total_consumption_kwh": round(float(total_kwh), 2),
        "active_alerts": alert_count,
        "building_count": len(buildings),
        "buildings": [BuildingResponse.model_validate(b).model_dump() for b in buildings],
        "subscription": SubscriptionResponse.model_validate(subscription).model_dump() if subscription else None,
        "devices": [DeviceResponse.model_validate(d).model_dump() for d in devices],
    }


@router.get("/stats", summary="Tenant aggregate statistics")
def get_tenant_stats(db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    """Return aggregate stats for the tenant overview dashboard."""
    tenants = db.query(Tenant).all()
    total = len(tenants)
    active = sum(1 for t in tenants if t.is_active)
    by_type = {}
    by_plan = {}
    for t in tenants:
        tt = t.tenant_type or "unknown"
        by_type[tt] = by_type.get(tt, 0) + 1
        sp = t.subscription_plan or "none"
        by_plan[sp] = by_plan.get(sp, 0) + 1

    total_devices = db.query(func.count(Device.id)).scalar() or 0
    total_consumption = db.query(func.sum(EnergyLog.consumption)).scalar() or 0
    active_alerts = db.query(func.count(TenantAlert.id)).scalar() or 0

    return {
        "total_tenants": total,
        "active_tenants": active,
        "by_type": by_type,
        "by_plan": by_plan,
        "total_devices": total_devices,
        "total_consumption_kwh": round(float(total_consumption), 2),
        "active_alerts": active_alerts,
    }


@router.get("/{tenant_id}", response_model=TenantResponse, summary="Get tenant by ID")
def get_tenant(tenant_id: int, db: Session = Depends(get_db)) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.get(
    "/unit/{unit_key}",
    response_model=TenantResponse,
    summary="Get tenant by unit_key",
)
def get_tenant_by_unit(unit_key: str, db: Session = Depends(get_db)) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.unit_key == unit_key).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.post(
    "/",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tenant",
)
def create_tenant(tenant_in: TenantCreate, db: Session = Depends(get_db), _admin: dict = Depends(require_admin)) -> Tenant:
    if db.query(Tenant).filter(Tenant.unit_key == tenant_in.unit_key).first():
        raise HTTPException(status_code=400, detail="unit_key already exists")
    if db.query(Tenant).filter(Tenant.email == tenant_in.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_tenant = Tenant(
        **tenant_in.model_dump(),
        plan_start_date=date.today(),
    )
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)

    # Auto-create a default subscription
    plan_key = tenant_in.subscription_plan or "basic"
    defaults = PLAN_DEFAULTS.get(plan_key, PLAN_DEFAULTS["basic"])
    sub = Subscription(
        tenant_id=new_tenant.id,
        plan=plan_key,
        max_devices=defaults["max_devices"],
        max_users=defaults["max_users"],
        max_buildings=defaults["max_buildings"],
        price_per_month=defaults["price"],
        starts_at=date.today(),
    )
    db.add(sub)
    db.commit()

    return new_tenant


@router.put("/{tenant_id}", response_model=TenantResponse, summary="Update a tenant")
def update_tenant(
    tenant_id: int,
    data: TenantUpdate,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    update_fields = data.model_dump(exclude_unset=True)

    if "unit_key" in update_fields and update_fields["unit_key"] != tenant.unit_key:
        if db.query(Tenant).filter(Tenant.unit_key == update_fields["unit_key"]).first():
            raise HTTPException(status_code=400, detail="unit_key already exists")

    if "email" in update_fields and update_fields["email"] != tenant.email:
        if db.query(Tenant).filter(Tenant.email == update_fields["email"]).first():
            raise HTTPException(status_code=400, detail="Email already registered")

    for field, value in update_fields.items():
        setattr(tenant, field, value)

    tenant.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(tenant)
    return tenant


@router.delete(
    "/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a tenant permanently",
)
def delete_tenant(tenant_id: int, db: Session = Depends(get_db), _admin: dict = Depends(require_admin)) -> None:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    # Delete related subscriptions, buildings, alerts, energy logs, devices first
    db.query(Subscription).filter(Subscription.tenant_id == tenant_id).delete()
    db.query(Building).filter(Building.tenant_id == tenant_id).delete()
    db.query(TenantAlert).filter(TenantAlert.unit_key == tenant.unit_key).delete()
    db.query(EnergyLog).filter(EnergyLog.unit_key == tenant.unit_key).delete()
    db.query(Device).filter(Device.unit_key == tenant.unit_key).delete()
    db.delete(tenant)
    db.commit()


# ══════════════════════════════════════════════════════════════════════════════
#  TENANT DETAIL — per-tenant aggregated data
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{tenant_id}/detail", summary="Full tenant detail with stats")
def get_tenant_detail(tenant_id: int, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    devices = db.query(Device).filter(Device.unit_key == tenant.unit_key).all()
    device_count = len(devices)

    total_kwh = (
        db.query(func.sum(EnergyLog.consumption))
        .filter(EnergyLog.unit_key == tenant.unit_key)
        .scalar()
    ) or 0

    alert_count = (
        db.query(func.count(TenantAlert.id))
        .filter(TenantAlert.unit_key == tenant.unit_key)
        .scalar()
    ) or 0

    buildings = db.query(Building).filter(Building.tenant_id == tenant_id, Building.is_active == True).all()
    subscription = (
        db.query(Subscription)
        .filter(Subscription.tenant_id == tenant_id, Subscription.status == "active")
        .first()
    )

    plan_info = PLAN_DEFAULTS.get(tenant.subscription_plan or "basic", PLAN_DEFAULTS["basic"])

    return {
        "tenant": TenantResponse.model_validate(tenant).model_dump(),
        "device_count": device_count,
        "device_limit": plan_info["max_devices"],
        "total_consumption_kwh": round(float(total_kwh), 2),
        "active_alerts": alert_count,
        "building_count": len(buildings),
        "buildings": [BuildingResponse.model_validate(b).model_dump() for b in buildings],
        "subscription": SubscriptionResponse.model_validate(subscription).model_dump() if subscription else None,
        "devices": [DeviceResponse.model_validate(d).model_dump() for d in devices],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  BUILDINGS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{tenant_id}/buildings", response_model=list[BuildingResponse], summary="List buildings")
def list_buildings(tenant_id: int, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return db.query(Building).filter(Building.tenant_id == tenant_id).all()


@router.post(
    "/{tenant_id}/buildings",
    response_model=BuildingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a building",
)
def create_building(tenant_id: int, data: BuildingCreate, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    building = Building(tenant_id=tenant_id, **data.model_dump())
    db.add(building)
    db.commit()
    db.refresh(building)
    return building


@router.put("/{tenant_id}/buildings/{building_id}", response_model=BuildingResponse)
def update_building(tenant_id: int, building_id: int, data: BuildingUpdate, db: Session = Depends(get_db)):
    b = db.query(Building).filter(Building.id == building_id, Building.tenant_id == tenant_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Building not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(b, k, v)
    db.commit()
    db.refresh(b)
    return b


# ══════════════════════════════════════════════════════════════════════════════
#  DEVICES (per tenant)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{tenant_id}/devices", response_model=list[DeviceResponse], summary="List devices")
def list_tenant_devices(tenant_id: int, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return db.query(Device).filter(Device.unit_key == tenant.unit_key).all()


# ══════════════════════════════════════════════════════════════════════════════
#  SUBSCRIPTION
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{tenant_id}/subscription", response_model=SubscriptionResponse, summary="Get subscription")
def get_subscription(tenant_id: int, db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter(
        Subscription.tenant_id == tenant_id, Subscription.status == "active"
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="No active subscription")
    return sub


@router.put("/{tenant_id}/subscription", response_model=SubscriptionResponse, summary="Update subscription")
def update_subscription(tenant_id: int, data: SubscriptionCreate, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Expire current active subscription
    current = db.query(Subscription).filter(
        Subscription.tenant_id == tenant_id, Subscription.status == "active"
    ).first()
    if current:
        current.status = "expired"
        current.ends_at = date.today()

    # Create new subscription
    defaults = PLAN_DEFAULTS.get(data.plan, PLAN_DEFAULTS["basic"])
    sub = Subscription(
        tenant_id=tenant_id,
        plan=data.plan,
        max_devices=defaults["max_devices"],
        max_users=defaults["max_users"],
        max_buildings=defaults["max_buildings"],
        price_per_month=defaults["price"],
        billing_cycle=data.billing_cycle,
        starts_at=date.today(),
    )
    db.add(sub)

    # Update tenant's plan field too
    tenant.subscription_plan = data.plan
    tenant.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(sub)
    return sub
