import json
from decimal import Decimal
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.database.database import get_async_db
from app.models.commerce import Contact, Customer, Order
from app.models.product import Product
from app.services.auth import decode_token

router = APIRouter(prefix='/api', tags=['orders'])

class OrderItem(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=100)

class OrderCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=120)
    customer_email: str = Field(min_length=5, max_length=180)
    customer_phone: str = Field(min_length=5, max_length=50)
    delivery_address: str = Field(min_length=5, max_length=1000)
    items: list[OrderItem] = Field(min_length=1, max_length=50)

class OrderStatusUpdate(BaseModel):
    status: str = Field(pattern=r'^(pending|confirmed|processing|ready|completed|cancelled)$')

class ContactPayload(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    contact_type: str = Field(pattern=r'^(phone|whatsapp|sms|email)$')
    value: str = Field(min_length=3, max_length=220)
    display_value: str | None = Field(default=None, max_length=220)
    active: bool = True
    sort_order: int = 0

def token_payload(authorization: str | None, role: str | None = None):
    if not authorization or not authorization.lower().startswith('bearer '):
        return None
    return decode_token(authorization.split(' ', 1)[1], role)

def require_admin(authorization: str | None = Header(default=None)):
    payload = token_payload(authorization, 'admin')
    if not payload:
        raise HTTPException(status_code=401, detail='Admin authentication required')
    return payload

@router.get('/business')
def business_settings():
    return {'email': settings.BUSINESS_EMAIL, 'phone': settings.BUSINESS_PHONE, 'whatsapp': settings.WHATSAPP_NUMBER, 'location': settings.BUSINESS_LOCATION}

@router.get('/contacts')
async def public_contacts(db: AsyncSession = Depends(get_async_db)):
    contacts = list((await db.scalars(select(Contact).where(Contact.active.is_(True)).order_by(Contact.sort_order.asc(), Contact.created_at.asc()))).all())
    return [{'id': item.id, 'label': item.label, 'contact_type': item.contact_type, 'value': item.value, 'display_value': item.display_value, 'active': item.active, 'sort_order': item.sort_order} for item in contacts]

@router.get('/admin/contacts', dependencies=[Depends(require_admin)])
async def admin_contacts(db: AsyncSession = Depends(get_async_db)):
    contacts = list((await db.scalars(select(Contact).order_by(Contact.sort_order.asc(), Contact.created_at.asc()))).all())
    return [{'id': item.id, 'label': item.label, 'contact_type': item.contact_type, 'value': item.value, 'display_value': item.display_value, 'active': item.active, 'sort_order': item.sort_order} for item in contacts]

@router.post('/admin/contacts', status_code=201, dependencies=[Depends(require_admin)])
async def create_contact(payload: ContactPayload, db: AsyncSession = Depends(get_async_db)):
    contact = Contact(**payload.model_dump())
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return {'id': contact.id, **payload.model_dump()}

@router.put('/admin/contacts/{contact_id}', dependencies=[Depends(require_admin)])
async def update_contact(contact_id: int, payload: ContactPayload, db: AsyncSession = Depends(get_async_db)):
    contact = await db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail='Contact not found')
    for key, value in payload.model_dump().items():
        setattr(contact, key, value)
    await db.commit()
    await db.refresh(contact)
    return {'id': contact.id, **payload.model_dump()}

@router.delete('/admin/contacts/{contact_id}', dependencies=[Depends(require_admin)])
async def delete_contact(contact_id: int, db: AsyncSession = Depends(get_async_db)):
    contact = await db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail='Contact not found')
    await db.delete(contact)
    await db.commit()
    return {'deleted': True, 'id': contact_id}

@router.post('/orders', status_code=201)
async def create_order(payload: OrderCreate, authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_async_db)):
    customer_payload = token_payload(authorization, 'customer')
    customer_id = int(customer_payload['sub']) if customer_payload else None
    product_ids = [item.product_id for item in payload.items]
    products = list((await db.scalars(select(Product).where(Product.id.in_(product_ids), Product.published.is_(True)))).all())
    by_id = {product.id: product for product in products}
    if len(by_id) != len(set(product_ids)):
        raise HTTPException(status_code=400, detail='One or more products are unavailable')
    lines = []
    total = Decimal('0')
    for item in payload.items:
        product = by_id[item.product_id]
        line_total = Decimal(str(product.price)) * item.quantity
        total += line_total
        lines.append({'product_id': product.id, 'name': product.name, 'quantity': item.quantity, 'unit_price': str(product.price), 'line_total': str(line_total)})
    order = Order(customer_id=customer_id, customer_name=payload.customer_name, customer_email=payload.customer_email, customer_phone=payload.customer_phone, delivery_address=payload.delivery_address, items_json=json.dumps(lines), total=total, status='pending')
    db.add(order)
    await db.commit()
    await db.refresh(order)
    order.order_reference = f"KT-{order.created_at.year}-{order.id:04d}"
    await db.commit()
    await db.refresh(order)
    return {'id': order.id, 'order_reference': order.order_reference, 'status': order.status, 'total': str(order.total), 'items': lines, 'created_at': order.created_at}

@router.get('/orders/me')
async def customer_orders(authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_async_db)):
    payload = token_payload(authorization, 'customer')
    if not payload:
        raise HTTPException(status_code=401, detail='Customer authentication required')
    orders = list((await db.scalars(select(Order).where(Order.customer_id == int(payload['sub'])).order_by(Order.created_at.desc()))).all())
    return [{'id': order.id, 'order_reference': order.order_reference or f"KT-{order.created_at.year}-{order.id:04d}", 'status': order.status, 'total': str(order.total), 'items': json.loads(order.items_json), 'created_at': order.created_at, 'delivery_address': order.delivery_address} for order in orders]

@router.get('/admin/orders', dependencies=[Depends(require_admin)])
async def admin_orders(db: AsyncSession = Depends(get_async_db)):
    orders = list((await db.scalars(select(Order).order_by(Order.created_at.desc()))).all())
    return [{'id': order.id, 'order_reference': order.order_reference or f"KT-{order.created_at.year}-{order.id:04d}", 'status': order.status, 'total': str(order.total), 'items': json.loads(order.items_json), 'customer_name': order.customer_name, 'customer_email': order.customer_email, 'customer_phone': order.customer_phone, 'delivery_address': order.delivery_address, 'created_at': order.created_at} for order in orders]

@router.patch('/admin/orders/{order_id}', dependencies=[Depends(require_admin)])
async def update_order_status(order_id: int, payload: OrderStatusUpdate, db: AsyncSession = Depends(get_async_db)):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail='Order not found')
    order.status = payload.status
    await db.commit()
    await db.refresh(order)
    return {'id': order.id, 'order_reference': order.order_reference or f"KT-{order.created_at.year}-{order.id:04d}", 'status': order.status}
