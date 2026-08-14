from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.database.database import get_async_db
from app.models.commerce import Banner

router = APIRouter(prefix='/api', tags=['commerce'])

def require_admin(x_admin_token: str | None = Header(default=None)):
    if not x_admin_token or x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Valid admin token required')
    return True

class BannerPayload(BaseModel):
    eyebrow: str = Field(default='Kentank', max_length=80)
    title: str = Field(min_length=1, max_length=180)
    body: str = ''
    image_url: str | None = None
    cta_label: str = 'Explore tanks'
    cta_url: str = '/catalogue'
    active: bool = True
    sort_order: int = 0

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
