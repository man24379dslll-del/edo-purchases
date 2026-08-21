"""
Хранение приложенных файлов (договоры, закупки и т.д.) + реестр документов
для страницы "Хранилище документов".

Файлы сохраняются на диск в settings.upload_dir под уникальным именем
(UUID + оригинальное расширение). При загрузке сразу создаётся запись в
таблице documents (пока без привязки к договору/закупке — сущность может
ещё не существовать на этот момент, форма заполняется постепенно). Привязка
происходит позже, при создании/доработке самого документа — см.
workflow.link_document(), который вызывается из contracts_router/purchases_router.

Отдача файла (GET) сделана БЕЗ обязательной авторизации: имя файла — это
непредсказуемый UUID, и раз мы кладём ссылку в <iframe>/<img> для превью,
это тот же уровень защиты, что был бы у произвольной вставленной пользователем
ссылки на Google Drive (тоже "просто ссылка"). Загрузка и поиск по реестру
требуют входа.
"""
import mimetypes
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app import models, schemas
from app.services.workflow import gen_id

router = APIRouter(prefix="/api/files", tags=["files"])
documents_router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".txt", ".csv", ".zip",
}


def _ensure_upload_dir():
    os.makedirs(settings.upload_dir, exist_ok=True)


def _safe_join(filename: str) -> str:
    """Не даёт выйти за пределы upload_dir через '../' в имени файла."""
    path = os.path.normpath(os.path.join(settings.upload_dir, filename))
    if not path.startswith(os.path.normpath(settings.upload_dir)):
        raise HTTPException(400, "Некорректное имя файла.")
    return path


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(get_current_user)):
    _ensure_upload_dir()

    original_name = file.filename or "file"
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Недопустимый тип файла: {ext or '(без расширения)'}."
                                  f" Разрешены: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    contents = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(400, f"Файл больше {settings.max_upload_mb} МБ.")

    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = _safe_join(unique_name)
    with open(dest_path, "wb") as f:
        f.write(contents)

    url = f"/api/files/{unique_name}"
    db.add(models.Document(
        id=gen_id(db, "ФАЙЛ"), stored_filename=unique_name, original_name=original_name,
        url=url, size_bytes=len(contents), uploaded_by=user.email,
    ))
    db.commit()

    return {
        "url": url,
        "filename": unique_name,
        "originalName": original_name,
        "sizeBytes": len(contents),
    }


@router.get("/{filename}")
def download_file(filename: str):
    path = _safe_join(filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "Файл не найден.")
    media_type, _ = mimetypes.guess_type(path)
    return FileResponse(path, media_type=media_type or "application/octet-stream")


@documents_router.get("", response_model=list[schemas.DocumentOut])
def list_documents(
    q: Optional[str] = None, entity_type: Optional[str] = None,
    db: Session = Depends(get_db), _=Depends(get_current_user),
):
    """Хранилище документов: поиск по имени файла, кто загрузил, к чему привязан."""
    query = db.query(models.Document)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            models.Document.original_name.ilike(like),
            models.Document.entity_subject.ilike(like),
            models.Document.entity_id.ilike(like),
            models.Document.uploaded_by.ilike(like),
        ))
    if entity_type:
        query = query.filter(models.Document.entity_type == entity_type)
    return query.order_by(models.Document.uploaded_at.desc()).limit(500).all()
