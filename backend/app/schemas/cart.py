from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CartItemModifier(BaseModel):
    name: str
    price: float


class CartItemChoice(BaseModel):
    group_id: str
    group_name: str
    option_id: str
    option_name: str
    price_delta: float = 0.0


class CartItemCreateRequest(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, le=100)
    selected_modifiers: Optional[List[Dict[str, Any]]] = []
    selected_choices: Optional[List[Dict[str, Any]]] = []
    removed_ingredients: Optional[List[str]] = []


class CartItemUpdateRequest(BaseModel):
    quantity: int = Field(ge=0, le=100)


class CartSettingsUpdateRequest(BaseModel):
    branch_id: Optional[str] = None
    order_type: Optional[str] = None  # DELIVERY or COLLECTION
    coupon_code: Optional[str] = None


class CartMergeRequest(BaseModel):
    guest_session_id: Optional[str] = None
    items: Optional[List[CartItemCreateRequest]] = None


class CartProductOut(BaseModel):
    id: str
    name: str
    sku: Optional[str] = None
    base_price: float
    image_url: Optional[str] = None
    is_active: bool = True
    category_id: Optional[str] = None

    class Config:
        from_attributes = True


class CartItemResponse(BaseModel):
    id: str
    cart_id: str
    product_id: str
    product: CartProductOut
    quantity: int
    selected_modifiers: List[Dict[str, Any]] = []
    selected_choices: List[Dict[str, Any]] = []
    removed_ingredients: List[str] = []
    unit_price: float
    line_total: float

    class Config:
        from_attributes = True


class CartResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    order_type: str = "COLLECTION"
    branch_id: Optional[str] = None
    coupon_code: Optional[str] = None
    items: List[CartItemResponse] = []
    subtotal: float = 0.0
    item_count: int = 0

    class Config:
        from_attributes = True
