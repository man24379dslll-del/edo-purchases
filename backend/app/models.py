from sqlalchemy import (
    Column, String, Boolean, Numeric, DateTime, Date, ForeignKey, BigInteger, Integer, Text
)
from sqlalchemy.sql import func
from app.database import Base

ALL_ROLES = ['Админ', 'Инициатор', 'Директор', 'Юрист', 'Бухгалтер']


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
    price_per_unit = Column(Numeric(16, 2), default=0)
    status = Column(String, nullable=False, default="На согласовании")
    is_standard = Column(Boolean)  # NULL пока Директор не решил; True/False после его решения на первом этапе
    valid_until = Column(Date)
    comment = Column(Text)
    file_url = Column(String)


class Approval(Base):
    """
    Этапы согласования договора. Цепочка динамическая (не фиксированная заранее):
    stage 0 — Директор (решает: "Стандартный" → финал, либо отправляет дальше)
    stage 1 — Юрист (создаётся только если Директор выбрал "не стандартный")
    stage 2 — Бухгалтер (создаётся после Юриста)
    stage 3 — Директор, финальная подпись (создаётся после Бухгалтера)
    """
    __tablename__ = "approvals"
    approval_id = Column(String, primary_key=True)
    contract_id = Column(String, ForeignKey("contracts.id"), nullable=False)
    stage = Column(Integer, nullable=False)
    approver_role = Column(String, nullable=False)
    approver_email = Column(String)
    decision = Column(String, nullable=False, default="Ожидает")
    decision_date = Column(DateTime(timezone=True))
    comment = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    state = Column(String, nullable=False, default="active")  # active | done | skipped


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


class Document(Base):
    """
    Реестр всех загруженных файлов — для страницы 'Хранилище документов'.
    Запись создаётся сразу при загрузке файла (entity_id ещё NULL, т.к. договор
    на этот момент может ещё не существовать), и дозаполняется при создании
    самого договора, когда известно, к чему файл относится.
    """
    __tablename__ = "documents"
    id = Column(String, primary_key=True)
    stored_filename = Column(String, nullable=False, unique=True)
    original_name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    size_bytes = Column(BigInteger)
    uploaded_by = Column(String, ForeignKey("users.email"))
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    entity_type = Column(String)
    entity_id = Column(String)
    entity_subject = Column(String)
