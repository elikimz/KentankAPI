from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

class ProductBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=140, pattern=r"^[a-z0-9-]+$")
    capacity_litres: int = Field(gt=0)
    category: str = Field(min_length=2, max_length=80)
    price: Decimal = Field(gt=0)
    note: str = Field(min_length=5)
    colour: str = Field(default="#e7dfd0", max_length=20)
    image_url: str | None = None
    featured: bool = False
    published: bool = True

class ProductCreate(ProductBase):
    pass

class ProductImageRead(BaseModel):
    id: int
    image_url: str
    alt_text: str
    sort_order: int
    model_config = ConfigDict(from_attributes=True)

class ProductRead(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ProductDetailRead(ProductRead):
    images: list[ProductImageRead] = []
    related_products: list[ProductRead] = []

class InquiryCreate(BaseModel):
    product_id: int | None = None
    customer_name: str = Field(min_length=2, max_length=120)
    contact: str = Field(min_length=3, max_length=180)
    message: str = Field(min_length=5, max_length=2000)

class InquiryRead(InquiryCreate):
    id: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
