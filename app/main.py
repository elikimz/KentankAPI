from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from app.api.routes.catalog import router as catalog_router
from app.api.routes.commerce import router as commerce_router
from app.core.config import settings
from app.database.base import Base
from app.database.database import engine, AsyncSessionLocal
from app.models.product import Product
from app.models.commerce import Banner, Customer, Order

async def seed_products():
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(select(Product).limit(1))
        if existing: return
        seed = [
            Product(name="The Household", slug="the-household", capacity_litres=1000, category="Household", price=22500, note="Compact, dependable storage for everyday family use.", colour="#e7dfd0", featured=True),
            Product(name="The Reserve", slug="the-reserve", capacity_litres=2000, category="Household", price=39800, note="A balanced choice for larger homes and steady supply.", colour="#d7c9b6", featured=True),
            Product(name="The Estate", slug="the-estate", capacity_litres=3000, category="Large capacity", price=57200, note="Built for generous storage without compromising footprint.", colour="#c9b69d", featured=True),
            Product(name="The Commercial", slug="the-commercial", capacity_litres=5000, category="Commercial", price=94500, note="Serious capacity for schools, farms, and businesses.", colour="#b79f84"),
            Product(name="The Farmstead", slug="the-farmstead", capacity_litres=10000, category="Commercial", price=179000, note="Long-term water security for demanding sites.", colour="#9f866e"),
        ]
        db.add_all(seed)
        await db.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_products()
    yield
    await engine.dispose()

app = FastAPI(title=settings.APP_NAME, version=settings.VERSION, description="Public catalogue and admin services for Kentank water storage.", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
@app.get("/")
def root(): return {"message": "Kentank API is running", "version": settings.VERSION}

@app.get("/health")
def health(): return {"status": "healthy"}

app.include_router(catalog_router)
app.include_router(commerce_router)
