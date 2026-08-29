from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr
from app.schemas.payment import PaymentResponse

class OrderItemCreate(BaseModel):
    product_id: str
    quantity: int = 1
    selected_modifiers: List[Dict[str, Any]] = []
    selected_choices: Optional[List[Dict[str, Any]]] = []

class OrderCreateRequest(BaseModel):
    branch_id: str
    order_type: str = "DELIVERY"  # DELIVERY or COLLECTION
    customer_name: str
    customer_email: EmailStr
    customer_phone: str
    delivery_address: Optional[Dict[str, Any]] = None
    collection_slot_time: Optional[str] = None
    delivery_instructions: Optional[str] = None
    items: List[OrderItemCreate]
    coupon_code: Optional[str] = None
    redeem_reward_id: Optional[str] = None
    redeem_points: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    delivery_postcode: Optional[str] = None

class OrderItemResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    total_price: float
    selected_modifiers: Optional[List[Dict[str, Any]]] = None
    selected_choices: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True

class OrderStatusHistoryResponse(BaseModel):
    id: str
    from_status: Optional[str] = None
    to_status: str
    notes: Optional[str] = None
    created_at: Any

    class Config:
        from_attributes = True

class OrderResponse(BaseModel):
    id: str
    order_number: str
    customer_id: Optional[str] = None
    customer_name: str
    customer_email: str
    customer_phone: str
    branch_id: str
    order_type: str
    status: str
    delivery_address: Optional[Dict[str, Any]] = None
    collection_slot_time: Optional[Any] = None
    delivery_instructions: Optional[str] = None
    subtotal: float
    delivery_fee: float
    service_fee: float
    discount_amount: float
    vat_amount: float
    total_amount: float
    payment_method: str
    payment_status: str
    payment_transaction_id: Optional[str] = None
    coupon_code: Optional[str] = None
    points_earned: int
    points_redeemed: int
    created_at: Any
    items: List[OrderItemResponse] = []
    status_history: List[OrderStatusHistoryResponse] = []
    payments: List[PaymentResponse] = []

    class Config:
        from_attributes = True


class StatusUpdateRequest(BaseModel):
    status: str
    notes: Optional[str] = None
