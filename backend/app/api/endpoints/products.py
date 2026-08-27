import random
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.product import Category, Product, ProductModifier, Inventory
from app.models.branch import Branch
from app.schemas.product import (
    CategoryResponse, CategoryCreateRequest, CategoryReorderRequest,
    ProductResponse, ProductCreateRequest, ProductUpdateRequest,
    InventoryResponse, InventoryUpdateRequest, InventoryToggleRequest
)
from app.api.endpoints.auth import require_role
from app.models.user import UserRole, User

router = APIRouter()

@router.get("/categories", response_model=List[CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    """Returns active menu categories sorted by display order."""
    return db.query(Category).filter(Category.is_active == True).order_by(Category.display_order.asc()).all()

@router.post("/categories", response_model=CategoryResponse)
def create_category(
    request: CategoryCreateRequest,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Admin create new menu category."""
    clean_name = request.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Category name cannot be empty.")

    slug_base = clean_name.lower().replace(" ", "-")
    slug_val = re.sub(r'[^a-z0-9\-]', '', slug_base) or "category"
    
    existing = db.query(Category).filter(Category.slug == slug_val).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.name = clean_name
            db.commit()
            db.refresh(existing)
            return existing
        while db.query(Category).filter(Category.slug == slug_val).first():
            slug_val = f"{slug_base[:80]}-{random.randint(100, 999)}"

    max_order = db.query(Category).count()

    category = Category(
        name=clean_name,
        slug=slug_val,
        icon=request.icon or "hamburger",
        display_order=request.display_order if request.display_order is not None else max_order,
        is_active=True
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category

@router.put("/categories/reorder", response_model=List[CategoryResponse])
def reorder_categories(
    request: CategoryReorderRequest,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Admin reorder menu categories display order."""
    for item in request.orders:
        cat = db.query(Category).filter(Category.id == item.id).first()
        if cat:
            cat.display_order = item.display_order
    db.commit()
    return db.query(Category).filter(Category.is_active == True).order_by(Category.display_order.asc()).all()

@router.delete("/categories/{category_id}")
def delete_category(
    category_id: str,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Admin delete category."""
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    prod_count = db.query(Product).filter(Product.category_id == category_id).count()
    if prod_count > 0:
        cat.is_active = False
        db.commit()
        return {"message": "Category archived successfully", "id": category_id}

    db.delete(cat)
    db.commit()
    return {"message": "Category deleted successfully", "id": category_id}

@router.get("/products", response_model=List[ProductResponse])
def list_products(
    category_id: Optional[str] = Query(None),
    branch_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Returns active products filtered by category and populated with branch inventory availability."""
    query = db.query(Product).filter(Product.is_active == True)
    if category_id:
        query = query.filter(Product.category_id == category_id)
    prods = query.all()

    inv_map = {}
    if branch_id and branch_id != "ALL":
        invs = db.query(Inventory).filter(Inventory.branch_id == branch_id).all()
        for inv in invs:
            inv_map[inv.product_id] = inv

    res = []
    for p in prods:
        inv = inv_map.get(p.id)
        if inv is not None:
            is_avail = bool(inv.is_available) and (inv.stock_quantity is None or inv.stock_quantity > 0)
            stock_qty = inv.stock_quantity if inv.stock_quantity is not None else 100
        else:
            is_avail = bool(getattr(p, 'is_available', True)) and bool(p.is_active)
            stock_qty = 100
        p_dict = {
            "id": p.id,
            "category_id": p.category_id,
            "name": p.name,
            "sku": p.sku,
            "short_description": p.short_description,
            "full_description": p.full_description,
            "allergens": p.allergens,
            "ingredients": p.ingredients,
            "image_url": p.image_url,
            "images": p.images or ([p.image_url] if p.image_url else []),
            "base_price": p.base_price,
            "compare_at_price": p.compare_at_price,
            "rating": p.rating,
            "reviews_count": p.reviews_count,
            "is_bestseller": p.is_bestseller,
            "has_tax": p.has_tax,
            "has_service_charge": p.has_service_charge,
            "vat_category": p.vat_category,
            "is_active": p.is_active,
            "is_available": is_avail,
            "stock_quantity": stock_qty,
            "modifiers": p.modifiers or []
        }
        res.append(ProductResponse(**p_dict))
    return res

@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product_details(
    product_id: str,
    branch_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Returns detailed product model with add-ons, modifiers, and branch inventory availability."""
    prod = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    is_avail = bool(getattr(prod, 'is_available', True)) and bool(prod.is_active)
    stock_qty = 100
    if branch_id and branch_id != "ALL":
        inv = db.query(Inventory).filter(Inventory.branch_id == branch_id, Inventory.product_id == product_id).first()
        if inv:
            is_avail = bool(inv.is_available) and (inv.stock_quantity is None or inv.stock_quantity > 0)
            stock_qty = inv.stock_quantity if inv.stock_quantity is not None else 100

    p_dict = {
        "id": prod.id,
        "category_id": prod.category_id,
        "name": prod.name,
        "sku": prod.sku,
        "short_description": prod.short_description,
        "full_description": prod.full_description,
        "allergens": prod.allergens,
        "ingredients": prod.ingredients,
        "image_url": prod.image_url,
        "images": prod.images or ([prod.image_url] if prod.image_url else []),
        "base_price": prod.base_price,
        "compare_at_price": prod.compare_at_price,
        "rating": prod.rating,
        "reviews_count": prod.reviews_count,
        "is_bestseller": prod.is_bestseller,
        "has_tax": prod.has_tax,
        "has_service_charge": prod.has_service_charge,
        "vat_category": prod.vat_category,
        "is_active": prod.is_active,
        "is_available": is_avail,
        "stock_quantity": stock_qty,
        "modifiers": prod.modifiers or []
    }
    return ProductResponse(**p_dict)

@router.post("/products", response_model=ProductResponse)
def create_product(
    request: ProductCreateRequest,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Super Admin create new product with modifiers, allergens, and default stock."""
    sku_candidate = request.sku.strip() if request.sku and request.sku.strip() else f"PROD-{random.randint(1000, 9999)}"
    if db.query(Product).filter(Product.sku == sku_candidate).first():
        sku_candidate = f"{sku_candidate}-{random.randint(100, 999)}"

    prod = Product(
        category_id=request.category_id,
        name=request.name,
        sku=sku_candidate,
        short_description=request.short_description,
        full_description=request.full_description,
        allergens=request.allergens,
        ingredients=request.ingredients,
        image_url=request.image_url,
        images=request.images if request.images is not None else ([request.image_url] if request.image_url else []),
        base_price=request.base_price,
        compare_at_price=request.compare_at_price,
        rating=request.rating or 4.7,
        is_bestseller=request.is_bestseller,
        has_tax=request.has_tax,
        has_service_charge=request.has_service_charge,
        is_active=True
    )
    db.add(prod)
    db.flush()

    if request.modifiers:
        for mod in request.modifiers:
            if mod.get("name"):
                m = ProductModifier(
                    product_id=prod.id,
                    name=mod.get("name"),
                    price=float(mod.get("price", 0.0))
                )
                db.add(m)

    db.commit()
    db.refresh(prod)
    return prod

@router.put("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str,
    request: ProductUpdateRequest,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Super Admin update product details, allergens, ingredients, image_url, rating, and bestseller status."""
    prod = db.query(Product).filter(Product.id == product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    if request.category_id is not None:
        prod.category_id = request.category_id
    if request.name is not None:
        prod.name = request.name
    if request.sku is not None and request.sku.strip():
        prod.sku = request.sku.strip()
    if request.short_description is not None:
        prod.short_description = request.short_description
    if request.full_description is not None:
        prod.full_description = request.full_description
    if request.allergens is not None:
        prod.allergens = request.allergens
    if request.ingredients is not None:
        prod.ingredients = request.ingredients
    if request.image_url is not None:
        prod.image_url = request.image_url
    if request.images is not None:
        prod.images = request.images
    if request.base_price is not None:
        prod.base_price = request.base_price
    if request.compare_at_price is not None:
        prod.compare_at_price = request.compare_at_price
    if request.rating is not None:
        prod.rating = request.rating
    if request.is_bestseller is not None:
        prod.is_bestseller = request.is_bestseller
    if request.has_tax is not None:
        prod.has_tax = request.has_tax
    if request.has_service_charge is not None:
        prod.has_service_charge = request.has_service_charge
    if request.is_active is not None:
        prod.is_active = request.is_active

    if request.modifiers is not None:
        db.query(ProductModifier).filter(ProductModifier.product_id == prod.id).delete()
        for mod in request.modifiers:
            if mod.get("name"):
                m = ProductModifier(
                    product_id=prod.id,
                    name=mod.get("name"),
                    price=float(mod.get("price", 0.0))
                )
                db.add(m)

    db.commit()
    db.refresh(prod)
    return prod

@router.delete("/products/{product_id}")
def delete_product(
    product_id: str,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Super Admin delete a product."""
    prod = db.query(Product).filter(Product.id == product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    from app.models.order import OrderItem
    order_items_count = db.query(OrderItem).filter(OrderItem.product_id == product_id).count()

    if order_items_count > 0:
        # Safe archiving to preserve historical order integrity and foreign keys
        prod.is_active = False
        db.query(Inventory).filter(Inventory.product_id == product_id).update({Inventory.is_available: False})
        db.commit()
        return {"message": "Product archived successfully", "id": product_id, "archived": True}
    else:
        # Hard delete if no historical orders exist for this product
        db.delete(prod)
        db.commit()
        return {"message": "Product deleted successfully", "id": product_id, "deleted": True}

# ==========================================
# BRANCH-ISOLATED INVENTORY & STOCK ENDPOINTS
# ==========================================

@router.get("/inventory", response_model=List[InventoryResponse])
def list_inventory(
    branch_id: Optional[str] = Query(None),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.BRANCH_ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Branch-Isolated Inventory list.
    Super Admin can view inventory for all branches or a specific branch.
    Branch Admin can view inventory ONLY for their assigned branch.
    """
    if current_user.role == UserRole.BRANCH_ADMIN:
        assigned_ids = [bu.branch_id for bu in current_user.branch_assignments]
        if branch_id and branch_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Access denied to this branch's inventory")
        target_branch_ids = assigned_ids
    else:
        if branch_id and branch_id != "ALL":
            target_branch_ids = [branch_id]
        else:
            branches = db.query(Branch).filter(Branch.is_active == True).all()
            target_branch_ids = [b.id for b in branches]

    # Auto-initialize missing inventory rows for active products
    active_products = db.query(Product).filter(Product.is_active == True).all()
    for bid in target_branch_ids:
        for p in active_products:
            exists = db.query(Inventory).filter(Inventory.branch_id == bid, Inventory.product_id == p.id).first()
            if not exists:
                inv = Inventory(
                    branch_id=bid,
                    product_id=p.id,
                    stock_quantity=100,
                    low_stock_threshold=10,
                    is_available=True
                )
                db.add(inv)
    db.commit()

    query = db.query(Inventory).join(Product).filter(
        Inventory.branch_id.in_(target_branch_ids),
        Product.is_active == True
    )
    items = query.all()

    result = []
    for inv in items:
        prod = inv.product
        cat = prod.category if prod else None
        result.append(InventoryResponse(
            id=inv.id,
            branch_id=inv.branch_id,
            product_id=inv.product_id,
            product_name=prod.name if prod else "Unknown",
            product_sku=prod.sku if prod else "",
            category_id=prod.category_id if prod else None,
            category_name=cat.name if cat else None,
            base_price=prod.base_price if prod else 0.0,
            image_url=prod.image_url if prod else None,
            stock_quantity=inv.stock_quantity,
            low_stock_threshold=inv.low_stock_threshold,
            is_available=inv.is_available
        ))
    return result

@router.patch("/inventory/{inventory_id}", response_model=InventoryResponse)
def update_inventory_item(
    inventory_id: str,
    request: InventoryUpdateRequest,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.BRANCH_ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Branch-Isolated Inventory update.
    Branch Admin can update stock/availability ONLY for their assigned branch.
    Super Admin can update stock/availability for any branch.
    """
    inv = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory record not found")

    if current_user.role == UserRole.BRANCH_ADMIN:
        assigned_ids = [bu.branch_id for bu in current_user.branch_assignments]
        if inv.branch_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Cannot manage inventory outside assigned branch")

    if request.stock_quantity is not None:
        inv.stock_quantity = max(0, request.stock_quantity)
    if request.low_stock_threshold is not None:
        inv.low_stock_threshold = max(0, request.low_stock_threshold)
    if request.is_available is not None:
        inv.is_available = request.is_available

    db.commit()
    db.refresh(inv)

    prod = inv.product
    cat = prod.category if prod else None
    return InventoryResponse(
        id=inv.id,
        branch_id=inv.branch_id,
        product_id=inv.product_id,
        product_name=prod.name if prod else "Unknown",
        product_sku=prod.sku if prod else "",
        category_id=prod.category_id if prod else None,
        category_name=cat.name if cat else None,
        base_price=prod.base_price if prod else 0.0,
        image_url=prod.image_url if prod else None,
        stock_quantity=inv.stock_quantity,
        low_stock_threshold=inv.low_stock_threshold,
        is_available=inv.is_available
    )

@router.post("/inventory/toggle", response_model=InventoryResponse)
def toggle_inventory_stock(
    request: InventoryToggleRequest,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.BRANCH_ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Toggle In-Stock / Out-of-Stock or update stock quantity for a product in a branch.
    Enforces strict branch isolation for Branch Admins.
    """
    if current_user.role == UserRole.BRANCH_ADMIN:
        assigned_ids = [bu.branch_id for bu in current_user.branch_assignments]
        if request.branch_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Cannot manage inventory outside assigned branch")

    inv = db.query(Inventory).filter(
        Inventory.branch_id == request.branch_id,
        Inventory.product_id == request.product_id
    ).first()

    if not inv:
        inv = Inventory(
            branch_id=request.branch_id,
            product_id=request.product_id,
            stock_quantity=request.stock_quantity if request.stock_quantity is not None else 100,
            low_stock_threshold=10,
            is_available=request.is_available if request.is_available is not None else True
        )
        db.add(inv)
    else:
        if request.is_available is not None:
            inv.is_available = request.is_available
        else:
            inv.is_available = not inv.is_available
        if request.stock_quantity is not None:
            inv.stock_quantity = max(0, request.stock_quantity)

    db.commit()
    db.refresh(inv)

    prod = inv.product or db.query(Product).filter(Product.id == request.product_id).first()
    cat = prod.category if prod else None
    return InventoryResponse(
        id=inv.id,
        branch_id=inv.branch_id,
        product_id=inv.product_id,
        product_name=prod.name if prod else "Unknown",
        product_sku=prod.sku if prod else "",
        category_id=prod.category_id if prod else None,
        category_name=cat.name if cat else None,
        base_price=prod.base_price if prod else 0.0,
        image_url=prod.image_url if prod else None,
        stock_quantity=inv.stock_quantity,
        low_stock_threshold=inv.low_stock_threshold,
        is_available=inv.is_available
    )


