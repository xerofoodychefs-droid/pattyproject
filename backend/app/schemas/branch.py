import math
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, field_validator

class BranchBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    address_line1: str
    postcode: str
    city: str = "London"
    latitude: float
    longitude: float
    phone: Optional[str] = None
    opening_hours: Optional[Dict[str, Any]] = None
    delivery_enabled: bool = True
    collection_enabled: bool = True
    ordering_enabled: bool = True
    delivery_radius_miles: float = 2.0
    is_active: bool = True

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if v is None or math.isnan(v) or math.isinf(v) or not (-90.0 <= v <= 90.0):
            raise ValueError("Latitude must be a valid float between -90.0 and +90.0")
        return round(float(v), 6)

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if v is None or math.isnan(v) or math.isinf(v) or not (-180.0 <= v <= 180.0):
            raise ValueError("Longitude must be a valid float between -180.0 and +180.0")
        return round(float(v), 6)

    @field_validator("delivery_radius_miles")
    @classmethod
    def validate_delivery_radius_miles(cls, v: float) -> float:
        return 2.0

class BranchCreate(BaseModel):
    code: Optional[str] = None
    name: str
    address_line1: str
    postcode: str
    city: str = "London"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = "020 7946 0000"
    opening_hours: Optional[Dict[str, Any]] = None
    delivery_enabled: bool = True
    collection_enabled: bool = True
    ordering_enabled: bool = True
    delivery_radius_miles: float = 2.0
    is_active: bool = True

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if math.isnan(v) or math.isinf(v) or not (-90.0 <= v <= 90.0):
                raise ValueError("Latitude must be a valid float between -90.0 and +90.0")
            return round(float(v), 6)
        return None

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if math.isnan(v) or math.isinf(v) or not (-180.0 <= v <= 180.0):
                raise ValueError("Longitude must be a valid float between -180.0 and +180.0")
            return round(float(v), 6)
        return None

    @field_validator("delivery_radius_miles")
    @classmethod
    def validate_delivery_radius_miles(cls, v: float) -> float:
        return 2.0

class BranchUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    address_line1: Optional[str] = None
    postcode: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    opening_hours: Optional[Dict[str, Any]] = None
    delivery_enabled: Optional[bool] = None
    collection_enabled: Optional[bool] = None
    ordering_enabled: Optional[bool] = None

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if math.isnan(v) or math.isinf(v) or not (-90.0 <= v <= 90.0):
                raise ValueError("Latitude must be a valid float between -90.0 and +90.0")
            return round(float(v), 6)
        return None

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if math.isnan(v) or math.isinf(v) or not (-180.0 <= v <= 180.0):
                raise ValueError("Longitude must be a valid float between -180.0 and +180.0")
            return round(float(v), 6)
        return None

class BranchResponse(BranchBase):
    id: str
    model_config = ConfigDict(from_attributes=True)

class NearestBranchInfo(BranchBase):
    id: str
    distance_miles: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)

class CandidateOutletInfo(BaseModel):
    id: str
    name: str
    code: Optional[str] = None
    address_line1: str
    city: str = "London"
    postcode: str
    distance_miles: Optional[float] = None
    delivery_eligible: bool = False
    collection_eligible: bool = True
    model_config = ConfigDict(from_attributes=True)

class NearestBranchRequest(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    postcode: Optional[str] = None
    fulfillment_method: Optional[str] = None

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if math.isnan(v) or math.isinf(v) or not (-90.0 <= v <= 90.0):
                raise ValueError("Latitude must be a valid float between -90.0 and +90.0")
            return round(float(v), 6)
        return None

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if math.isnan(v) or math.isinf(v) or not (-180.0 <= v <= 180.0):
                raise ValueError("Longitude must be a valid float between -180.0 and +180.0")
            return round(float(v), 6)
        return None

    @field_validator("fulfillment_method")
    @classmethod
    def validate_fulfillment_method(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip().upper()
            if clean not in ["DELIVERY", "COLLECTION"]:
                raise ValueError("fulfillment_method must be either DELIVERY or COLLECTION")
            return clean
        return None

class NearestBranchResponse(BaseModel):
    assigned_branch: Optional[NearestBranchInfo] = None
    nearest_branch: Optional[NearestBranchInfo] = None
    candidate_outlets: Optional[List[CandidateOutletInfo]] = None
    distance_miles: Optional[float] = None
    is_delivery_eligible: bool = False
    delivery_available: bool = False
    collection_available: bool = True
    status: str
    message: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class BranchStatsResponse(BaseModel):
    branch_id: str
    code: str
    name: str
    total_orders: int
    completed_orders: int
    cancelled_orders: int
    pending_orders: int
    model_config = ConfigDict(from_attributes=True)

