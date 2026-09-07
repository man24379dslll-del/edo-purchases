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
    contractor_id: Optional[str] = None


class UserOut(BaseModel):
    email: str
    fio: str
    role: str
    is_active: bool
    contractor_id: Optional[str] = None

    class Config:
        from_attributes = True


class AddUserIn(BaseModel):
    email: EmailStr
    fio: str
    role: str
    password: Optional[str] = None
    contractor_id: Optional[str] = None  # обязательно, если role == "Контрагент"


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
    amount: Optional[Decimal] = None  # сумма договора — может быть не известна заранее
    category: str = "Прочее"
    contract_type: str = "Системный"
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
    amount: Optional[float] = None
    category: str
    contract_type: str
    approval_tier: Optional[int] = None
    status: str
    valid_until: Optional[date] = None
    comment: Optional[str] = None
    file_url: Optional[str] = None

    class Config:
        from_attributes = True


class DecisionIn(BaseModel):
    contract_id: str
    decision: str            # Согласовано | Отклонено
    comment: Optional[str] = None


class AttachDocumentIn(BaseModel):
    url: str
    doc_type: str
    description: Optional[str] = None


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
    doc_type: Optional[str] = None

    class Config:
        from_attributes = True


class PaymentScheduleItemIn(BaseModel):
    contract_id: str
    due_date: date
    amount: Decimal
    comment: Optional[str] = None


class PaymentScheduleItemOut(BaseModel):
    id: str
    contract_id: str
    due_date: date
    amount: float
    status: str
    comment: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    paid_at: Optional[datetime] = None
    # для удобного отображения в календаре без второго запроса за договором:
    contract_subject: Optional[str] = None
    contractor_name: Optional[str] = None

    class Config:
        from_attributes = True
