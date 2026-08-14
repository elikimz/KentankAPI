from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.database.database import get_async_db
from app.models.inquiry import Inquiry
from app.models.product import Product
from app.models.commerce import ProductImage
from app.services.auth import decode_token
from app.schemas.catalog import InquiryCreate, InquiryRead, ProductCreate, ProductDetailRead, ProductRead

router = APIRouter(prefix="/api", tags=["catalog"])

def require_admin(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith('bearer ') or not decode_token(authorization.split(' ', 1)[1], 'admin'):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Admin authentication required')
    return True

@router.get("/products", response_model=list[ProductRead])
async def list_products(category: str | None = None, featured: bool | None = None, q: str | None = Query(default=None, max_length=80), db: AsyncSession = Depends(get_async_db)):
    query = select(Product).where(Product.published.is_(True)).order_by(Product.featured.desc(), Product.capacity_litres.asc())
    if category and category != "All tanks": query = query.where(Product.category == category)
    if featured is not None: query = query.where(Product.featured == featured)
    if q: query = query.where(Product.name.ilike(f"%{q}%"))
    return list((await db.scalars(query)).all())

@router.get("/products/{slug}", response_model=ProductDetailRead)
async def get_product(slug: str, db: AsyncSession = Depends(get_async_db)):
    product = await db.scalar(select(Product).where(Product.slug == slug, Product.published.is_(True)))
    if not product: raise HTTPException(status_code=404, detail="Product not found")
    images = list((await db.scalars(select(ProductImage).where(ProductImage.product_id == product.id).order_by(ProductImage.sort_order.asc()))).all())
    related = list((await db.scalars(select(Product).where(Product.category == product.category, Product.id != product.id, Product.published.is_(True)).order_by(Product.featured.desc(), Product.capacity_litres.asc()).limit(4))).all())
    return {**ProductRead.model_validate(product).model_dump(), 'images': images, 'related_products': related}

@router.post("/inquiries", response_model=InquiryRead, status_code=201)
async def create_inquiry(payload: InquiryCreate, db: AsyncSession = Depends(get_async_db)):
    inquiry = Inquiry(**payload.model_dump())
    db.add(inquiry)
    await db.commit()
    await db.refresh(inquiry)
    return inquiry

@router.get("/admin/products", response_model=list[ProductRead], dependencies=[Depends(require_admin)])
async def admin_products(db: AsyncSession = Depends(get_async_db)):
    return list((await db.scalars(select(Product).order_by(Product.capacity_litres.asc()))).all())

@router.post("/admin/products", response_model=ProductRead, status_code=201, dependencies=[Depends(require_admin)])
async def create_product(payload: ProductCreate, db: AsyncSession = Depends(get_async_db)):
    if await db.scalar(select(Product).where(Product.slug == payload.slug)):
        raise HTTPException(status_code=409, detail="A product with this slug already exists")
    product = Product(**payload.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product

@router.put("/admin/products/{product_id}", response_model=ProductRead, dependencies=[Depends(require_admin)])
async def update_product(product_id: int, payload: ProductCreate, db: AsyncSession = Depends(get_async_db)):
    product = await db.get(Product, product_id)
    if not product: raise HTTPException(status_code=404, detail="Product not found")
    for key, value in payload.model_dump().items(): setattr(product, key, value)
    await db.commit()
    await db.refresh(product)
    return product

@router.delete("/admin/products/{product_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_product(product_id: int, db: AsyncSession = Depends(get_async_db)):
    product = await db.get(Product, product_id)
    if not product: raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(product)
    await db.commit()

@router.get("/admin/inquiries", response_model=list[InquiryRead], dependencies=[Depends(require_admin)])
async def admin_inquiries(db: AsyncSession = Depends(get_async_db)):
    return list((await db.scalars(select(Inquiry).order_by(Inquiry.created_at.desc()))).all())
