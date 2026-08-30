from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

from app.core.database import get_db
from app.api.endpoints.auth import require_role
from app.models.user import User, UserRole
from app.models.loyalty import LoyaltyAccount, LoyaltyTransaction
from app.models.order import Order
from app.schemas.customer import AdminCustomerResponse, AdminCustomerDetailResponse

router = APIRouter()


@router.get("", response_model=List[AdminCustomerResponse])
@router.get("/", response_model=List[AdminCustomerResponse])
def list_customers(
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.BRANCH_ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Authoritative list of registered customers with real database loyalty balances and order counts.
    Strictly branch-isolated for BRANCH_ADMIN and global for SUPER_ADMIN.
    """
    # 1. Base query for verified customers (excluding admin accounts)
    query = (
        db.query(User)
        .options(joinedload(User.loyalty_account))
        .filter(
            User.email_verified.is_(True),
            or_(
                func.upper(User.role) == UserRole.CUSTOMER,
                User.role.is_(None),
                ~func.upper(User.role).in_([UserRole.SUPER_ADMIN, UserRole.BRANCH_ADMIN])
            )
        )
    )

    assigned_branch_ids = []
    if current_user.role == UserRole.BRANCH_ADMIN:
        assigned_branch_ids = [bu.branch_id for bu in current_user.branch_assignments]
        if not assigned_branch_ids:
            return []

        # Scope customers: only users who have at least one order placed at one of assigned_branch_ids
        cust_ids_with_orders = db.query(Order.customer_id).filter(
            Order.branch_id.in_(assigned_branch_ids),
            Order.customer_id.isnot(None)
        )
        cust_emails_with_orders = db.query(func.lower(Order.customer_email)).filter(
            Order.branch_id.in_(assigned_branch_ids),
            Order.customer_email.isnot(None)
        )
        query = query.filter(
            or_(
                User.id.in_(cust_ids_with_orders),
                func.lower(User.email).in_(cust_emails_with_orders)
            )
        )

    if search:
        s = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(User.full_name).like(s),
                func.lower(User.email).like(s),
                User.phone.like(s)
            )
        )

    users = query.order_by(User.created_at.desc()).all()

    # Batch aggregation of order counts
    order_query_by_id = db.query(Order.customer_id, func.count(Order.id)).filter(Order.customer_id.isnot(None))
    order_query_by_email = db.query(func.lower(Order.customer_email), func.count(Order.id)).filter(Order.customer_id.is_(None))

    if current_user.role == UserRole.BRANCH_ADMIN:
        order_query_by_id = order_query_by_id.filter(Order.branch_id.in_(assigned_branch_ids))
        order_query_by_email = order_query_by_email.filter(Order.branch_id.in_(assigned_branch_ids))

    order_counts_by_id = dict(order_query_by_id.group_by(Order.customer_id).all())
    order_counts_by_email = dict(order_query_by_email.group_by(func.lower(Order.customer_email)).all())

    customers = []
    for u in users:
        loyalty = u.loyalty_account
        pts = loyalty.available_points if loyalty else 0
        lt_pts = loyalty.lifetime_points if loyalty else 0
        
        email_clean = u.email.strip().lower() if u.email else ""
        total_orders = order_counts_by_id.get(u.id, 0) + order_counts_by_email.get(email_clean, 0)

        customers.append(
            AdminCustomerResponse(
                id=u.id,
                name=u.full_name,
                email=u.email,
                phone=u.phone,
                orders=total_orders,
                points=pts,
                lifetime_points=lt_pts,
                is_active=u.is_active,
                created_at=u.created_at
            )
        )

    return customers


@router.get("/{customer_id}", response_model=AdminCustomerDetailResponse)
def get_customer_detail(
    customer_id: str,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.BRANCH_ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Authoritative single-customer profile with recent orders and loyalty transaction history.
    Strictly branch-isolated for BRANCH_ADMIN and global for SUPER_ADMIN.
    """
    user = (
        db.query(User)
        .options(joinedload(User.loyalty_account))
        .filter(
            User.id == customer_id,
            User.email_verified.is_(True),
            ~func.upper(User.role).in_([UserRole.SUPER_ADMIN, UserRole.BRANCH_ADMIN])
        )
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    assigned_branch_ids = []
    if current_user.role == UserRole.BRANCH_ADMIN:
        assigned_branch_ids = [bu.branch_id for bu in current_user.branch_assignments]
        if not assigned_branch_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )

        # Branch isolation check: Customer must have at least one order placed at one of assigned_branch_ids
        has_branch_order = db.query(Order.id).filter(
            or_(
                Order.customer_id == user.id,
                func.lower(Order.customer_email) == user.email.strip().lower()
            ),
            Order.branch_id.in_(assigned_branch_ids)
        ).first() is not None

        if not has_branch_order:
            # Return 404 to avoid leaking customer existence across branches
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )

    loyalty = user.loyalty_account
    pts = loyalty.available_points if loyalty else 0
    lt_pts = loyalty.lifetime_points if loyalty else 0
    tier = loyalty.tier if loyalty and loyalty.tier else "BRONZE"

    # Recent orders query
    orders_query = (
        db.query(Order)
        .filter(
            or_(
                Order.customer_id == user.id,
                func.lower(Order.customer_email) == user.email.strip().lower()
            )
        )
    )
    if current_user.role == UserRole.BRANCH_ADMIN:
        orders_query = orders_query.filter(Order.branch_id.in_(assigned_branch_ids))

    total_orders = orders_query.count()
    recent_orders = [
        {
            "id": o.id,
            "order_number": o.order_number,
            "status": o.status,
            "total_amount": o.total_amount,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "order_type": o.order_type
        }
        for o in orders_query.order_by(Order.created_at.desc()).limit(10).all()
    ]

    # Loyalty transaction history (Branch Admins only see transactions for orders at their branch)
    loyalty_txs = []
    if loyalty:
        tx_query = db.query(LoyaltyTransaction).filter(
            LoyaltyTransaction.loyalty_account_id == loyalty.id
        )
        if current_user.role == UserRole.BRANCH_ADMIN:
            branch_order_ids_sub = db.query(Order.id).filter(
                or_(
                    Order.customer_id == user.id,
                    func.lower(Order.customer_email) == user.email.strip().lower()
                ),
                Order.branch_id.in_(assigned_branch_ids)
            )
            tx_query = tx_query.filter(LoyaltyTransaction.order_id.in_(branch_order_ids_sub))

        txs = tx_query.order_by(LoyaltyTransaction.created_at.desc()).limit(20).all()
        loyalty_txs = [
            {
                "id": tx.id,
                "points": tx.points,
                "transaction_type": tx.transaction_type,
                "description": tx.description,
                "resulting_balance": tx.resulting_balance,
                "created_at": tx.created_at.isoformat() if tx.created_at else None
            }
            for tx in txs
        ]

    return AdminCustomerDetailResponse(
        id=user.id,
        name=user.full_name,
        email=user.email,
        phone=user.phone,
        orders=total_orders,
        points=pts,
        lifetime_points=lt_pts,
        tier=tier,
        is_active=user.is_active,
        created_at=user.created_at,
        recent_orders=recent_orders,
        loyalty_transactions=loyalty_txs
    )
