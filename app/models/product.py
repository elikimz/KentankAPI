from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    capacity_litres: Mapped[int] = mapped_column(nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    colour: Mapped[str] = mapped_column(String(20), default="#e7dfd0", nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    availability_status: Mapped[str] = mapped_column(String(40), default='In stock', nullable=False)
    variants_json: Mapped[str] = mapped_column(Text, default='[]', nullable=False)
    specifications_json: Mapped[str] = mapped_column(Text, default='{}', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
