from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.database.database import get_async_db
from app.models.commerce import AdminUser, Customer
from app.services.auth import create_token, decode_token, hash_password, verify_password

router = APIRouter(prefix='/api/auth', tags=['auth'])

class RegisterPayload(BaseModel):
    email: str
    full_name: str = Field(min_length=2, max_length=120)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        if '@' not in value or '.' not in value.rsplit('@', 1)[-1]:
            raise ValueError('Valid email required')
        return value.lower().strip()
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=50)

class LoginPayload(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        if '@' not in value or '.' not in value.rsplit('@', 1)[-1]:
            raise ValueError('Valid email required')
        return value.lower().strip()

class AdminProvisionPayload(RegisterPayload):
    setup_token: str = Field(min_length=8)

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    role: str
    user: dict


def bearer_payload(authorization: str | None, role: str | None = None):
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail='Bearer token required')
    payload = decode_token(authorization.split(' ', 1)[1], role)
    if not payload:
        raise HTTPException(status_code=401, detail='Invalid or expired token')
    return payload

@router.post('/admin/provision', response_model=AuthResponse, status_code=201)
async def provision_admin(payload: AdminProvisionPayload, db: AsyncSession = Depends(get_async_db)):
    if not settings.ADMIN_SETUP_TOKEN or payload.setup_token != settings.ADMIN_SETUP_TOKEN:
        raise HTTPException(status_code=403, detail='Invalid admin setup token')
    if await db.scalar(select(AdminUser).where(AdminUser.email == payload.email)):
        raise HTTPException(status_code=409, detail='Admin account already exists')
    admin = AdminUser(email=payload.email, full_name=payload.full_name, password_hash=hash_password(payload.password))
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return {'access_token': create_token(str(admin.id), 'admin'), 'role': 'admin', 'user': {'id': admin.id, 'email': admin.email, 'full_name': admin.full_name}}

@router.post('/admin/login', response_model=AuthResponse)
async def admin_login(payload: LoginPayload, db: AsyncSession = Depends(get_async_db)):
    admin = await db.scalar(select(AdminUser).where(AdminUser.email == payload.email, AdminUser.active.is_(True)))
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=401, detail='Invalid email or password')
    return {'access_token': create_token(str(admin.id), 'admin'), 'role': 'admin', 'user': {'id': admin.id, 'email': admin.email, 'full_name': admin.full_name}}

@router.post('/register', response_model=AuthResponse, status_code=201)
async def register_customer(payload: RegisterPayload, db: AsyncSession = Depends(get_async_db)):
    if await db.scalar(select(Customer).where(Customer.email == payload.email)):
        raise HTTPException(status_code=409, detail='An account with this email already exists')
    customer = Customer(email=payload.email, full_name=payload.full_name, phone=payload.phone, password_hash=hash_password(payload.password))
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return {'access_token': create_token(str(customer.id), 'customer'), 'role': 'customer', 'user': {'id': customer.id, 'email': customer.email, 'full_name': customer.full_name, 'phone': customer.phone}}

@router.post('/login', response_model=AuthResponse)
async def customer_login(payload: LoginPayload, db: AsyncSession = Depends(get_async_db)):
    customer = await db.scalar(select(Customer).where(Customer.email == payload.email))
    if not customer or not verify_password(payload.password, customer.password_hash):
        raise HTTPException(status_code=401, detail='Invalid email or password')
    return {'access_token': create_token(str(customer.id), 'customer'), 'role': 'customer', 'user': {'id': customer.id, 'email': customer.email, 'full_name': customer.full_name, 'phone': customer.phone}}

@router.get('/me')
async def current_user(authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_async_db)):
    payload = bearer_payload(authorization)
    model = AdminUser if payload['role'] == 'admin' else Customer
    user = await db.get(model, int(payload['sub']))
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return {'id': user.id, 'email': user.email, 'full_name': user.full_name, 'role': payload['role'], 'phone': getattr(user, 'phone', None)}
