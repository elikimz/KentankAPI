import hashlib
import hmac
import time
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.database.database import get_async_db
from app.models.commerce import Banner, Category, ProductImage
from app.models.product import Product
from app.services.auth import decode_token

router = APIRouter(prefix='/api', tags=['commerce'])

def require_admin(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith('bearer ') or not decode_token(authorization.split(' ', 1)[1], 'admin'):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Admin authentication required')
    return True

class BannerPayload(BaseModel):
    eyebrow: str = Field(default='Kentank', max_length=80)
    title: str = Field(min_length=1, max_length=180)
    body: str = ''
    image_url: str | None = None
    cta_label: str = 'Explore tanks'
    cta_url: str = '/catalogue'
    placement: str = 'home_hero'
    active: bool = True
    sort_order: int = 0

class CloudinarySignature(BaseModel):
    cloud_name: str
    api_key: str
    timestamp: int
    folder: str
    signature: str

class ProductImagePayload(BaseModel):
    id: int | None = None
    image_url: str = Field(min_length=10, max_length=500)
    alt_text: str = 'Kentank product image'
    sort_order: int = 0
    is_primary: bool = False
    model_config = {'from_attributes': True}

class CategoryPayload(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    slug: str = Field(min_length=2, max_length=120, pattern=r'^[a-z0-9-]+$')
    description: str = ''
    active: bool = True
    sort_order: int = 0

@router.post('/admin/uploads/signature', response_model=CloudinarySignature, dependencies=[Depends(require_admin)])
async def cloudinary_signature():
    if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY or not settings.CLOUDINARY_API_SECRET:
        raise HTTPException(status_code=503, detail='Cloudinary is not configured on the server')
    timestamp = int(time.time())
    folder = settings.CLOUDINARY_FOLDER
    params = f'folder={folder}&timestamp={timestamp}'
    signature = hmac.new(settings.CLOUDINARY_API_SECRET.encode(), params.encode(), hashlib.sha1).hexdigest()
    return CloudinarySignature(cloud_name=settings.CLOUDINARY_CLOUD_NAME, api_key=settings.CLOUDINARY_API_KEY, timestamp=timestamp, folder=folder, signature=signature)

@router.get('/admin/products/{product_id}/images', response_model=list[ProductImagePayload], dependencies=[Depends(require_admin)])
async def admin_product_images(product_id: int, db: AsyncSession = Depends(get_async_db)):
    return list((await db.scalars(select(ProductImage).where(ProductImage.product_id == product_id).order_by(ProductImage.is_primary.desc(), ProductImage.sort_order.asc()))).all())

@router.post('/admin/products/{product_id}/images', response_model=ProductImagePayload, status_code=201, dependencies=[Depends(require_admin)])
async def add_product_image(product_id: int, payload: ProductImagePayload, db: AsyncSession = Depends(get_async_db)):
    product = await db.get(Product, product_id)
    if not product: raise HTTPException(status_code=404, detail='Product not found')
    images = list((await db.scalars(select(ProductImage).where(ProductImage.product_id == product_id))).all())
    has_primary = any(image.is_primary for image in images)
    make_primary = payload.is_primary or (not product.image_url and not has_primary)
    if make_primary:
        for image in images: image.is_primary = False
    image = ProductImage(product_id=product_id, image_url=payload.image_url, alt_text=payload.alt_text, sort_order=payload.sort_order, is_primary=make_primary)
    db.add(image)
    if make_primary:
        product.image_url = image.image_url
    await db.commit(); await db.refresh(image)
    return image

@router.put('/admin/products/{product_id}/images/{image_id}', response_model=ProductImagePayload, dependencies=[Depends(require_admin)])
async def update_product_image(product_id: int, image_id: int, payload: ProductImagePayload, db: AsyncSession = Depends(get_async_db)):
    image = await db.get(ProductImage, image_id)
    if not image or image.product_id != product_id: raise HTTPException(status_code=404, detail='Image not found')
    if payload.is_primary:
        images = list((await db.scalars(select(ProductImage).where(ProductImage.product_id == product_id))).all())
        for item in images: item.is_primary = False
    for key, value in payload.model_dump().items(): setattr(image, key, value)
    if image.is_primary:
        product = await db.get(Product, product_id)
        product.image_url = image.image_url
    await db.commit(); await db.refresh(image)
    return image

@router.delete('/admin/products/{product_id}/images/{image_id}', status_code=204, dependencies=[Depends(require_admin)])
async def delete_product_image(product_id: int, image_id: int, db: AsyncSession = Depends(get_async_db)):
    image = await db.get(ProductImage, image_id)
    if not image or image.product_id != product_id: raise HTTPException(status_code=404, detail='Image not found')
    product = await db.get(Product, product_id)
    was_primary = image.is_primary
    await db.delete(image)
    if was_primary and product:
        replacement = await db.scalar(select(ProductImage).where(ProductImage.product_id == product_id, ProductImage.id != image_id).order_by(ProductImage.sort_order.asc()))
        if replacement:
            replacement.is_primary = True
            product.image_url = replacement.image_url
        else:
            product.image_url = None
    await db.commit()

@router.get('/categories', response_model=list[CategoryPayload])
async def list_categories(db: AsyncSession = Depends(get_async_db)):
    return list((await db.scalars(select(Category).where(Category.active.is_(True)).order_by(Category.sort_order.asc(), Category.name.asc()))).all())

@router.get('/admin/categories', dependencies=[Depends(require_admin)])
async def admin_categories(db: AsyncSession = Depends(get_async_db)):
    return list((await db.scalars(select(Category).order_by(Category.sort_order.asc(), Category.name.asc()))).all())

@router.post('/admin/categories', response_model=CategoryPayload, status_code=201, dependencies=[Depends(require_admin)])
async def create_category(payload: CategoryPayload, db: AsyncSession = Depends(get_async_db)):
    if await db.scalar(select(Category).where((Category.slug == payload.slug) | (Category.name == payload.name))):
        raise HTTPException(status_code=409, detail='Category already exists')
    category = Category(**payload.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category

@router.put('/admin/categories/{category_id}', response_model=CategoryPayload, dependencies=[Depends(require_admin)])
async def update_category(category_id: int, payload: CategoryPayload, db: AsyncSession = Depends(get_async_db)):
    category = await db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail='Category not found')
    for key, value in payload.model_dump().items():
        setattr(category, key, value)
    await db.commit()
    await db.refresh(category)
    return category

@router.delete('/admin/categories/{category_id}', status_code=204, dependencies=[Depends(require_admin)])
async def delete_category(category_id: int, db: AsyncSession = Depends(get_async_db)):
    category = await db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail='Category not found')
    await db.delete(category)
    await db.commit()

@router.get('/banners', response_model=list[BannerPayload])
async def list_banners(db: AsyncSession = Depends(get_async_db)):
    return list((await db.scalars(select(Banner).where(Banner.active.is_(True)).order_by(Banner.sort_order.asc(), Banner.created_at.desc()))).all())

@router.get('/admin/banners', dependencies=[Depends(require_admin)])
async def admin_banners(db: AsyncSession = Depends(get_async_db)):
    return list((await db.scalars(select(Banner).order_by(Banner.sort_order.asc(), Banner.created_at.desc()))).all())

@router.post('/admin/banners', response_model=BannerPayload, status_code=201, dependencies=[Depends(require_admin)])
async def create_banner(payload: BannerPayload, db: AsyncSession = Depends(get_async_db)):
    banner = Banner(**payload.model_dump())
    db.add(banner)
    await db.commit()
    await db.refresh(banner)
    return banner

@router.put('/admin/banners/{banner_id}', response_model=BannerPayload, dependencies=[Depends(require_admin)])
async def update_banner(banner_id: int, payload: BannerPayload, db: AsyncSession = Depends(get_async_db)):
    banner = await db.get(Banner, banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail='Banner not found')
    for key, value in payload.model_dump().items():
        setattr(banner, key, value)
    await db.commit()
    await db.refresh(banner)
    return banner

@router.delete('/admin/banners/{banner_id}', status_code=204, dependencies=[Depends(require_admin)])
async def delete_banner(banner_id: int, db: AsyncSession = Depends(get_async_db)):
    banner = await db.get(Banner, banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail='Banner not found')
    await db.delete(banner)
    await db.commit()
