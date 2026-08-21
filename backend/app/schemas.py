from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, EmailStr


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    fio: str
    role: str


class UserOut(BaseModel):
    email: str
    fio: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class AddUserIn(BaseModel):
    email: EmailStr
    fio: str
    role: str
    password: Optional[str] = None


class LegalEntityIn(BaseModel):
    name: str
    inn: Optional[str] = None
    address: Optional[str] = None


class LegalEntityOut(LegalEntityIn):
    id: str

    class Config:
        from_attributes = True


class ContractorIn(BaseModel):
    name: str
    inn: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None


class ContractCreateIn(BaseModel):
    contractor_name: str
    contractor_inn: Optional[str] = None
    legal_entity_id: Optional[str] = None
    subject: str
    contract_number: Optional[str] = None
    price_per_unit: Decimal = Decimal("0")
    valid_until: Optional[date] = None
    comment: Optional[str] = None
    file_url: Optional[str] = None


class ContractOut(BaseModel):
    id: str
    created_at: datetime
    initiator_email: str
    initiator_fio: str
    contractor_id: str
    contractor_name: str
    contractor_inn: Optional[str] = None
    legal_entity_id: Optional[str] = None
    legal_entity_name: Optional[str] = None
    subject: str
    contract_number: Optional[str] = None
    price_per_unit: float
    status: str
    is_standard: Optional[bool] = None
    valid_until: Optional[date] = None
    comment: Optional[str] = None
    file_url: Optional[str] = None

    class Config:
        from_attributes = True


class DecisionIn(BaseModel):
    contract_id: str
    decision: str            # Согласовано | Отклонено
    comment: Optional[str] = None
    # Заполняется только Директором на первом этапе рассмотрения:
    # True = "Стандартный" (сразу финал), False = "Отправить Юристу и Бухгалтеру".
    standard: Optional[bool] = None


class DocumentOut(BaseModel):
    id: str
    original_name: str
    url: str
    size_bytes: Optional[int] = None
    uploaded_by: Optional[str] = None
    uploaded_at: datetime
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    entity_subject: Optional[str] = None

    class Config:
        from_attributes = True
