from typing import Optional, List
from pydantic import BaseModel

class ProductModifierResponse(BaseModel):
    id: str
    name: str
    price: float
    is_required: bool
    is_active: bool

    class Config:
        from_attributes = True

class ProductChoiceOptionResponse(BaseModel):
    id: str
    group_id: str
    name: str
    price_delta: float = 0.0
    is_active: bool = True
    display_order: int = 0

    class Config:
        from_attributes = True

class ProductChoiceGroupResponse(BaseModel):
    id: str
    product_id: str
    name: str
    min_selections: int = 1
    max_selections: int = 1
    is_required: bool = True
    display_order: int = 0
    options: List[ProductChoiceOptionResponse] = []

    class Config:
        from_attributes = True

class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    icon: Optional[str] = None
    display_order: int

    class Config:
        from_attributes = True

class CategoryCreateRequest(BaseModel):
    name: str
    icon: Optional[str] = None
    display_order: Optional[int] = 0

class CategoryReorderItem(BaseModel):
    id: str
    display_order: int

class CategoryReorderRequest(BaseModel):
    orders: List[CategoryReorderItem]

class ProductResponse(BaseModel):
    id: str
    category_id: str
    name: str
    sku: str
    short_description: Optional[str] = None
    full_description: Optional[str] = None
    allergens: Optional[str] = None
    ingredients: Optional[str] = None
    image_url: Optional[str] = None
    images: Optional[List[str]] = []
    base_price: float
    compare_at_price: Optional[float] = None
    rating: float
    reviews_count: int
    is_bestseller: bool
    has_tax: bool
    has_service_charge: bool
    vat_category: str
    is_active: bool
    is_available: bool = True
    is_out_of_stock: bool = False
    stock_quantity: int = 100
    modifiers: List[ProductModifierResponse] = []
    choice_groups: List[ProductChoiceGroupResponse] = []

    class Config:
        from_attributes = True

class ProductCreateRequest(BaseModel):
    category_id: str
    name: str
    sku: Optional[str] = None
    short_description: Optional[str] = None
    full_description: Optional[str] = None
    allergens: Optional[str] = None
    ingredients: Optional[str] = None
    image_url: Optional[str] = None
    images: Optional[List[str]] = []
    base_price: float
    compare_at_price: Optional[float] = None
    rating: Optional[float] = 4.7
    is_bestseller: bool = False
    has_tax: bool = True
    has_service_charge: bool = False
    is_out_of_stock: Optional[bool] = False
    stock_quantity: int = 100
    modifiers: List[dict] = []
    choice_groups: Optional[List[dict]] = None

class ProductUpdateRequest(BaseModel):
    category_id: Optional[str] = None
    name: Optional[str] = None
    sku: Optional[str] = None
    short_description: Optional[str] = None
    full_description: Optional[str] = None
    allergens: Optional[str] = None
    ingredients: Optional[str] = None
    image_url: Optional[str] = None
    images: Optional[List[str]] = None
    base_price: Optional[float] = None
    compare_at_price: Optional[float] = None
    rating: Optional[float] = None
    is_bestseller: Optional[bool] = None
    has_tax: Optional[bool] = None
    has_service_charge: Optional[bool] = None
    is_active: Optional[bool] = None
    is_out_of_stock: Optional[bool] = None
    modifiers: Optional[List[dict]] = None
    choice_groups: Optional[List[dict]] = None

class ProductAvailabilityUpdateRequest(BaseModel):
    is_out_of_stock: bool

class CategoryAvailabilityUpdateRequest(BaseModel):
    is_out_of_stock: bool

class CategoryAvailabilityResponse(BaseModel):
    category_id: str
    is_out_of_stock: bool
    updated_products_count: int
    message: str

class InventoryResponse(BaseModel):
    id: str
    branch_id: str
    product_id: str
    product_name: str
    product_sku: str
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    base_price: float
    image_url: Optional[str] = None
    stock_quantity: int
    low_stock_threshold: int
    is_available: bool

    class Config:
        from_attributes = True

class InventoryUpdateRequest(BaseModel):
    stock_quantity: Optional[int] = None
    low_stock_threshold: Optional[int] = None
    is_available: Optional[bool] = None

class InventoryToggleRequest(BaseModel):
    branch_id: str
    product_id: str
    is_available: Optional[bool] = None
    stock_quantity: Optional[int] = None

