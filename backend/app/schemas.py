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


class ContractItemIn(BaseModel):
    name: str
    price: Decimal
    unit: Optional[str] = None


class ContractCreateIn(BaseModel):
    contractor_name: str
    contractor_inn: Optional[str] = None
    legal_entity_id: Optional[str] = None
    subject: str
    contract_number: Optional[str] = None
    limit_amount: Decimal = Decimal("0")
    valid_until: Optional[date] = None
    comment: Optional[str] = None
    needs_marketing: bool = False
    file_url: Optional[str] = None
    items: list[ContractItemIn] = []


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
    limit_amount: float
    status: str
    needs_marketing: bool
    valid_until: Optional[date] = None
    comment: Optional[str] = None
    file_url: Optional[str] = None
    revision: int = 1

    class Config:
        from_attributes = True


class PurchaseCreateIn(BaseModel):
    contract_id: Optional[str] = None
    purchase_type: str
    subcategory: Optional[str] = None
    subject: str
    quantity: Decimal
    price_per_unit: Decimal
    comment: Optional[str] = None
    file_url: Optional[str] = None


class PurchaseOut(BaseModel):
    id: str
    created_at: datetime
    initiator_email: str
    initiator_fio: str
    contract_id: Optional[str] = None
    contractor_name: Optional[str] = None
    purchase_type: Optional[str] = None
    subcategory: Optional[str] = None
    subject: str
    quantity: float
    price_per_unit: float
    amount: float
    status: str
    comment: Optional[str] = None
    file_url: Optional[str] = None
    execution_status: Optional[str] = None
    execution_date: Optional[datetime] = None
    revision: int = 1

    class Config:
        from_attributes = True


class DecisionIn(BaseModel):
    entity_type: str  # contract | purchase | amendment
    entity_id: str
    decision: str     # Согласовано | Отклонено
    comment: Optional[str] = None


class BulkDecisionItem(BaseModel):
    entity_type: str
    entity_id: str


class BulkDecisionIn(BaseModel):
    items: list[BulkDecisionItem]
    decision: str
    comment: Optional[str] = None


class ReceiptIn(BaseModel):
    purchase_id: str
    quantity: Decimal
    comment: Optional[str] = None


class PaymentIn(BaseModel):
    purchase_id: str
    amount: Decimal
    payment_type: Optional[str] = None
    payment_form: Optional[str] = None
    comment: Optional[str] = None


class AmendmentCreateIn(BaseModel):
    contract_id: str
    subject: str
    comment: Optional[str] = None
    needs_marketing: bool = False
    file_url: Optional[str] = None


class DelegationIn(BaseModel):
    delegator_email: EmailStr
    delegate_email: EmailStr
    starts_at: datetime
    ends_at: datetime
    comment: Optional[str] = None


class ResubmitIn(BaseModel):
    """Доработка отклонённого документа: те же поля, что при создании, плюс обязательный комментарий."""
    subject: Optional[str] = None
    comment: str
    limit_amount: Optional[Decimal] = None
    valid_until: Optional[date] = None
    file_url: Optional[str] = None
    quantity: Optional[Decimal] = None
    price_per_unit: Optional[Decimal] = None
