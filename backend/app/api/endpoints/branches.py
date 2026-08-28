from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.branch import Branch
from app.models.order import Order, OrderStatus
from app.schemas.branch import (
    BranchResponse,
    BranchCreate,
    BranchUpdate,
    NearestBranchRequest,
    NearestBranchResponse,
    NearestBranchInfo,
    BranchStatsResponse
)
from app.api.endpoints.auth import require_role
from app.models.user import UserRole, User
from app.services.branch_service import (
    find_nearest_eligible_branch,
    is_valid_coordinate,
    resolve_postcode_lat_lng,
    MAX_DELIVERY_RADIUS_MILES
)
from app.models.audit import AuditLog
import random

router = APIRouter()

@router.get("", response_model=List[BranchResponse])
@router.get("/", response_model=List[BranchResponse])
def list_public_branches(db: Session = Depends(get_db)):
    """Returns active public branches."""
    return db.query(Branch).filter(Branch.is_active == True).all()

@router.get("/stats", response_model=List[BranchStatsResponse])
@router.get("/stats/", response_model=List[BranchStatsResponse])
def get_branch_order_stats(
    response: Response,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.BRANCH_ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Authoritative real-time order statistics calculated from PostgreSQL for each branch.
    Guaranteed route ordering before parameterized /{branch_id} endpoints to avoid path collisions.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    branches_query = db.query(Branch).filter(Branch.is_active == True)
    if current_user.role == UserRole.BRANCH_ADMIN:
        assigned_ids = [bu.branch_id for bu in current_user.branch_assignments]
        branches_query = branches_query.filter(Branch.id.in_(assigned_ids))

    active_branches = branches_query.all()
    results = []

    for b in active_branches:
        total = db.query(func.count(Order.id)).filter(Order.branch_id == b.id).scalar() or 0
        completed = db.query(func.count(Order.id)).filter(
            Order.branch_id == b.id,
            Order.status.in_([OrderStatus.DELIVERED, OrderStatus.COLLECTED])
        ).scalar() or 0
        cancelled = db.query(func.count(Order.id)).filter(
            Order.branch_id == b.id,
            Order.status.in_([
                OrderStatus.CANCELLED,
                OrderStatus.REFUNDED,
                OrderStatus.REFUND_PENDING,
                OrderStatus.REJECTED
            ])
        ).scalar() or 0
        pending = db.query(func.count(Order.id)).filter(
            Order.branch_id == b.id,
            Order.status.in_([
                OrderStatus.INCOMING,
                OrderStatus.PENDING_PAYMENT,
                OrderStatus.PAID,
                OrderStatus.ACCEPTED,
                OrderStatus.PREPARING,
                OrderStatus.READY,
                OrderStatus.OUT_FOR_DELIVERY,
                OrderStatus.READY_FOR_COLLECTION
            ])
        ).scalar() or 0

        results.append(BranchStatsResponse(
            branch_id=b.id,
            code=b.code,
            name=b.name,
            total_orders=total,
            completed_orders=completed,
            cancelled_orders=cancelled,
            pending_orders=pending
        ))

    return results

@router.post("", response_model=BranchResponse)
@router.post("/", response_model=BranchResponse)
def create_branch(
    request: BranchCreate,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Super Admin create new branch with coordinate validation and auto-geocoding."""
    code_val = request.code.upper().strip() if request.code else "".join([w[0] for w in request.name.split()][:2]).upper()
    if not code_val:
        code_val = f"B{random.randint(10, 99)}"

    if db.query(Branch).filter(Branch.code == code_val).first():
        code_val = f"{code_val}{random.randint(1, 9)}"

    # Validate or geocode coordinates
    lat = request.latitude
    lng = request.longitude

    if lat is not None or lng is not None:
        if not is_valid_coordinate(lat, lng):
            raise HTTPException(
                status_code=400,
                detail="Invalid coordinates. Latitude must be between -90 and 90, and longitude between -180 and 180."
            )
    else:
        resolved = resolve_postcode_lat_lng(request.postcode)
        if not resolved or not is_valid_coordinate(resolved[0], resolved[1]):
            raise HTTPException(
                status_code=400,
                detail=f"Could not determine valid coordinates for postcode '{request.postcode}'. Please provide valid latitude and longitude or a valid UK postcode."
            )
        lat, lng = resolved

    branch = Branch(
        code=code_val,
        name=request.name.strip(),
        address_line1=request.address_line1.strip(),
        postcode=request.postcode.strip().upper(),
        city=request.city or "London",
        latitude=lat,
        longitude=lng,
        phone=request.phone or "020 7946 0000",
        delivery_enabled=request.delivery_enabled,
        collection_enabled=request.collection_enabled,
        ordering_enabled=request.ordering_enabled,
        delivery_radius_miles=MAX_DELIVERY_RADIUS_MILES,
        is_active=True
    )
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return branch

@router.put("/{branch_id}", response_model=BranchResponse)
@router.patch("/{branch_id}", response_model=BranchResponse)
def update_branch(
    branch_id: str,
    request: BranchUpdate,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.BRANCH_ADMIN])),
    db: Session = Depends(get_db)
):
    """Update existing branch details with coordinate validation."""
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    if current_user.role == UserRole.BRANCH_ADMIN:
        assigned_ids = [bu.branch_id for bu in current_user.branch_assignments]
        if branch_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="You do not have permission to manage this branch")

    if request.name is not None:
        branch.name = request.name.strip()
    if request.code is not None:
        branch.code = request.code.upper().strip()
    if request.address_line1 is not None:
        branch.address_line1 = request.address_line1.strip()
    if request.city is not None:
        branch.city = request.city.strip()
    if request.phone is not None:
        branch.phone = request.phone.strip()
    if request.opening_hours is not None:
        branch.opening_hours = request.opening_hours
    if request.delivery_enabled is not None:
        branch.delivery_enabled = request.delivery_enabled
    if request.collection_enabled is not None:
        branch.collection_enabled = request.collection_enabled
    if request.ordering_enabled is not None:
        branch.ordering_enabled = request.ordering_enabled

    # Coordinate & Postcode updates
    if request.latitude is not None or request.longitude is not None:
        new_lat = request.latitude if request.latitude is not None else branch.latitude
        new_lng = request.longitude if request.longitude is not None else branch.longitude
        if not is_valid_coordinate(new_lat, new_lng):
            raise HTTPException(
                status_code=400,
                detail="Invalid coordinates. Latitude must be between -90 and 90, and longitude between -180 and 180."
            )
        branch.latitude = new_lat
        branch.longitude = new_lng
    elif request.postcode is not None and request.postcode.strip().upper() != branch.postcode.upper():
        new_postcode = request.postcode.strip().upper()
        resolved = resolve_postcode_lat_lng(new_postcode)
        if not resolved or not is_valid_coordinate(resolved[0], resolved[1]):
            raise HTTPException(
                status_code=400,
                detail=f"Could not determine valid coordinates for postcode '{request.postcode}'. Please provide valid latitude and longitude or a valid UK postcode."
            )
        branch.latitude, branch.longitude = resolved

    if request.postcode is not None:
        branch.postcode = request.postcode.strip().upper()

    branch.delivery_radius_miles = MAX_DELIVERY_RADIUS_MILES
    db.commit()
    db.refresh(branch)
    return branch

@router.post("/nearest", response_model=NearestBranchResponse)
def get_nearest_branch(request: NearestBranchRequest, db: Session = Depends(get_db)):
    """Determines nearest eligible branch using Haversine distance & delivery radius validation."""
    result = find_nearest_eligible_branch(
        db=db,
        lat=request.latitude,
        lng=request.longitude,
        postcode=request.postcode,
        fulfillment_method=request.fulfillment_method
    )
    
    nearest_b = result.get("nearest_branch")
    assigned_b = result.get("assigned_branch")
    dist_val = result.get("distance_miles")
    candidates_val = result.get("candidate_outlets")

    nearest_info = None
    if nearest_b:
        nearest_info = NearestBranchInfo(
            id=getattr(nearest_b, "id", "") or "",
            code=getattr(nearest_b, "code", "") or "",
            name=getattr(nearest_b, "name", "") or "Branch",
            address_line1=getattr(nearest_b, "address_line1", "") or "",
            postcode=getattr(nearest_b, "postcode", "") or "",
            city=getattr(nearest_b, "city", None) or "London",
            latitude=getattr(nearest_b, "latitude", None) or 0.0,
            longitude=getattr(nearest_b, "longitude", None) or 0.0,
            phone=getattr(nearest_b, "phone", None),
            opening_hours=getattr(nearest_b, "opening_hours", None),
            delivery_enabled=getattr(nearest_b, "delivery_enabled", True) if getattr(nearest_b, "delivery_enabled", None) is not None else True,
            collection_enabled=getattr(nearest_b, "collection_enabled", True) if getattr(nearest_b, "collection_enabled", None) is not None else True,
            ordering_enabled=getattr(nearest_b, "ordering_enabled", True) if getattr(nearest_b, "ordering_enabled", None) is not None else True,
            delivery_radius_miles=getattr(nearest_b, "delivery_radius_miles", 2.0) or 2.0,
            is_active=bool(getattr(nearest_b, "is_active", True)) if getattr(nearest_b, "is_active", None) is not None else True,
            distance_miles=dist_val
        )

    assigned_info = None
    if assigned_b:
        assigned_info = NearestBranchInfo(
            id=getattr(assigned_b, "id", "") or "",
            code=getattr(assigned_b, "code", "") or "",
            name=getattr(assigned_b, "name", "") or "Branch",
            address_line1=getattr(assigned_b, "address_line1", "") or "",
            postcode=getattr(assigned_b, "postcode", "") or "",
            city=getattr(assigned_b, "city", None) or "London",
            latitude=getattr(assigned_b, "latitude", None) or 0.0,
            longitude=getattr(assigned_b, "longitude", None) or 0.0,
            phone=getattr(assigned_b, "phone", None),
            opening_hours=getattr(assigned_b, "opening_hours", None),
            delivery_enabled=getattr(assigned_b, "delivery_enabled", True) if getattr(assigned_b, "delivery_enabled", None) is not None else True,
            collection_enabled=getattr(assigned_b, "collection_enabled", True) if getattr(assigned_b, "collection_enabled", None) is not None else True,
            ordering_enabled=getattr(assigned_b, "ordering_enabled", True) if getattr(assigned_b, "ordering_enabled", None) is not None else True,
            delivery_radius_miles=getattr(assigned_b, "delivery_radius_miles", 2.0) or 2.0,
            is_active=bool(getattr(assigned_b, "is_active", True)) if getattr(assigned_b, "is_active", None) is not None else True,
            distance_miles=dist_val
        )

    return NearestBranchResponse(
        assigned_branch=assigned_info,
        nearest_branch=nearest_info,
        candidate_outlets=candidates_val,
        distance_miles=dist_val,
        is_delivery_eligible=result.get("is_delivery_eligible", False),
        delivery_available=result.get("delivery_available", False),
        collection_available=result.get("collection_available", True),
        status=result.get("status"),
        message=result.get("message")
    )


@router.patch("/{branch_id}/toggle-ordering", response_model=BranchResponse)
def toggle_branch_ordering(
    branch_id: str,
    ordering_enabled: bool,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.BRANCH_ADMIN])),
    db: Session = Depends(get_db)
):
    """Emergency ordering toggle for branch admin / super admin."""
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    # Branch Admin RBAC isolation check
    if current_user.role == UserRole.BRANCH_ADMIN:
        assigned_ids = [bu.branch_id for bu in current_user.branch_assignments]
        if branch_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="You do not have permission to manage this branch")

    old_state = branch.ordering_enabled
    branch.ordering_enabled = ordering_enabled
    
    # Record Audit Log
    audit = AuditLog(
        actor_id=current_user.id,
        actor_email=current_user.email,
        action="TOGGLE_BRANCH_ORDERING",
        resource="branches",
        resource_id=branch.id,
        diff_json={"old_ordering_enabled": old_state, "new_ordering_enabled": ordering_enabled}
    )
    db.add(audit)
    db.commit()
    db.refresh(branch)
    return branch

@router.delete("/{branch_id}")
def delete_branch(
    branch_id: str,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Super Admin delete branch with cleanup and audit trail."""
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    try:
        from app.models.branch import BranchUser, CollectionSlot
        from app.models.product import Inventory
        from app.models.printer import Printer, PrintJob
        from app.models.order import Order

        # Clean up related records
        db.query(BranchUser).filter(BranchUser.branch_id == branch_id).delete(synchronize_session=False)
        db.query(CollectionSlot).filter(CollectionSlot.branch_id == branch_id).delete(synchronize_session=False)
        db.query(Inventory).filter(Inventory.branch_id == branch_id).delete(synchronize_session=False)
        db.query(Printer).filter(Printer.branch_id == branch_id).delete(synchronize_session=False)
        db.query(PrintJob).filter(PrintJob.branch_id == branch_id).delete(synchronize_session=False)

        # Audit log before deletion
        audit = AuditLog(
            actor_id=current_user.id,
            actor_email=current_user.email,
            action="DELETE_BRANCH",
            resource="branches",
            resource_id=branch_id,
            diff_json={"branch_name": branch.name, "branch_code": branch.code}
        )
        db.add(audit)

        # Check if there are orders linked to this branch
        has_orders = db.query(Order).filter(Order.branch_id == branch_id).first() is not None
        if not has_orders:
            db.delete(branch)
        else:
            branch.is_active = False

        db.commit()
    except Exception as e:
        db.rollback()
        # Fallback to soft delete
        branch = db.query(Branch).filter(Branch.id == branch_id).first()
        if branch:
            branch.is_active = False
            db.commit()

    return {"message": "Branch deleted successfully", "id": branch_id}
