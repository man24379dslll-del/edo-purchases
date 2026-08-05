from sqlalchemy import (
    Column, String, Boolean, Numeric, DateTime, Date, ForeignKey, BigInteger, Integer, Text
)
from sqlalchemy.sql import func
from app.database import Base

ALL_ROLES = ['Админ', 'Инициатор', 'Закупщик', 'Маркетинг', 'Юрист',
             'Фин. директор', 'Директор', 'Бухгалтер', 'Склад']


class User(Base):
    __tablename__ = "users"
    email = Column(String, primary_key=True)
    fio = Column(String, nullable=False)
    role = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LegalEntity(Base):
    __tablename__ = "legal_entities"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    inn = Column(String)
    address = Column(String)


class Contractor(Base):
    __tablename__ = "contractors"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    inn = Column(String)
    contact_person = Column(String)
    contact_phone = Column(String)
    contact_email = Column(String)
    status = Column(String, default="Активен")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Contract(Base):
    __tablename__ = "contracts"
    id = Column(String, primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    initiator_email = Column(String, ForeignKey("users.email"), nullable=False)
    initiator_fio = Column(String, nullable=False)
    contractor_id = Column(String, ForeignKey("contractors.id"), nullable=False)
    contractor_name = Column(String, nullable=False)
    contractor_inn = Column(String)
    legal_entity_id = Column(String, ForeignKey("legal_entities.id"))
    legal_entity_name = Column(String)
    subject = Column(Text, nullable=False)
    contract_number = Column(String)
    limit_amount = Column(Numeric(16, 2), default=0)
    status = Column(String, nullable=False, default="На согласовании")
    needs_marketing = Column(Boolean, nullable=False, default=False)
    valid_until = Column(Date)
    comment = Column(Text)
    file_url = Column(String)
    revision = Column(Integer, nullable=False, default=1)


class ContractItem(Base):
    __tablename__ = "contract_items"
    id = Column(String, primary_key=True)
    contract_id = Column(String, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    price = Column(Numeric(16, 2), default=0)
    unit = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(String, ForeignKey("users.email"))


class ContractFile(Base):
    __tablename__ = "contract_files"
    id = Column(String, primary_key=True)
    contract_id = Column(String, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String, nullable=False)
    file_url = Column(String, nullable=False)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    uploaded_by = Column(String, ForeignKey("users.email"))


class Amendment(Base):
    __tablename__ = "amendments"
    id = Column(String, primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    initiator_email = Column(String, ForeignKey("users.email"), nullable=False)
    initiator_fio = Column(String, nullable=False)
    contract_id = Column(String, ForeignKey("contracts.id"), nullable=False)
    contractor_name = Column(String)
    subject = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="На согласовании")
    needs_marketing = Column(Boolean, nullable=False, default=False)
    comment = Column(Text)
    file_url = Column(String)
    revision = Column(Integer, nullable=False, default=1)


class Purchase(Base):
    __tablename__ = "purchases"
    id = Column(String, primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    initiator_email = Column(String, ForeignKey("users.email"), nullable=False)
    initiator_fio = Column(String, nullable=False)
    contract_id = Column(String, ForeignKey("contracts.id"))
    contractor_name = Column(String)
    purchase_type = Column(String)
    subcategory = Column(String)
    subject = Column(Text, nullable=False)
    quantity = Column(Numeric(16, 3), default=0)
    price_per_unit = Column(Numeric(16, 2), default=0)
    amount = Column(Numeric(16, 2), default=0)
    status = Column(String, nullable=False, default="На согласовании")
    comment = Column(Text)
    file_url = Column(String)
    execution_status = Column(String, default="Не исполнено")
    execution_date = Column(DateTime(timezone=True))
    revision = Column(Integer, nullable=False, default=1)


class Receipt(Base):
    __tablename__ = "receipts"
    id = Column(String, primary_key=True)
    purchase_id = Column(String, ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False)
    date = Column(DateTime(timezone=True), server_default=func.now())
    user_email = Column(String, ForeignKey("users.email"))
    user_fio = Column(String)
    quantity = Column(Numeric(16, 3), nullable=False)
    comment = Column(Text)


class Payment(Base):
    __tablename__ = "payments"
    id = Column(String, primary_key=True)
    purchase_id = Column(String, ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False)
    date = Column(DateTime(timezone=True), server_default=func.now())
    user_email = Column(String, ForeignKey("users.email"))
    user_fio = Column(String)
    amount = Column(Numeric(16, 2), nullable=False)
    payment_type = Column(String)
    payment_form = Column(String)
    comment = Column(Text)


class Approval(Base):
    __tablename__ = "approvals"
    approval_id = Column(String, primary_key=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    stage = Column(Integer, nullable=False)
    approver_role = Column(String, nullable=False)
    approver_email = Column(String)
    decision = Column(String, nullable=False, default="Ожидает")
    decision_date = Column(DateTime(timezone=True))
    comment = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    activated_at = Column(DateTime(timezone=True))
    deadline = Column(DateTime(timezone=True))
    escalated = Column(Boolean, nullable=False, default=False)
    revision = Column(Integer, nullable=False, default=1)
    signature = Column(String)
    state = Column(String, nullable=False, default="active")


class Delegation(Base):
    __tablename__ = "delegations"
    id = Column(String, primary_key=True)
    delegator_email = Column(String, ForeignKey("users.email"), nullable=False)
    delegator_role = Column(String, nullable=False)
    delegate_email = Column(String, ForeignKey("users.email"), nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    comment = Column(Text)
    created_by = Column(String, ForeignKey("users.email"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LogEntry(Base):
    __tablename__ = "log_entries"
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user_email = Column(String)
    role = Column(String)
    action = Column(String, nullable=False)
    entity_type = Column(String)
    entity_id = Column(String)
    comment = Column(Text)


class IdCounter(Base):
    """Общий атомарный счётчик для генерации человекочитаемых ID (см. services/workflow.gen_id)."""
    __tablename__ = "id_counters"
    name = Column(String, primary_key=True)
    value = Column(BigInteger, nullable=False, default=0)
