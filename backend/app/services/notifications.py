"""
Уведомления по email о новых задачах на согласование и об эскалации.

Best-effort: если SMTP не настроен (нет SMTP_HOST в переменных окружения) —
функции тихо ничего не делают. Ошибки отправки только логируются в stdout и
никогда не прерывают бизнес-логику (согласование не должно падать из-за
недоступного почтового сервера).

Настройка (переменные окружения Railway/локальный .env):
  SMTP_HOST, SMTP_PORT (по умолчанию 587), SMTP_USER, SMTP_PASSWORD,
  SMTP_FROM (адрес отправителя), APP_BASE_URL (для ссылок в письмах).
"""
import os
import smtplib
import ssl
from email.message import EmailMessage

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "edo@example.com")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5173")

ENTITY_LABEL = {"contract": "Договор", "purchase": "Закупка", "amendment": "Доп. соглашение"}
ENTITY_ROUTE = {"contract": "contracts", "purchase": "purchases", "amendment": "contracts"}

# Позволяет тестам подменить транспорт и проверить содержимое писем без реального SMTP.
_last_sent = []


def is_configured() -> bool:
    return bool(SMTP_HOST)


def send_email(to_email: str, subject: str, body: str) -> bool:
    _last_sent.append({"to": to_email, "subject": subject, "body": body})
    if not is_configured():
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg.set_content(body)
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls(context=context)
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:  # noqa: BLE001 — намеренно широкий catch, почта не должна ронять запрос
        print(f"[notifications] не удалось отправить письмо на {to_email}: {e}")
        return False


def notify_new_stage(db, entity_type: str, entity_id: str, role: str, subject: str):
    """Уведомляет всех пользователей с данной ролью о новом документе на согласование."""
    from app import models  # локальный импорт, чтобы избежать циклической зависимости
    users = db.query(models.User).filter(models.User.role == role, models.User.is_active.is_(True)).all()
    label = ENTITY_LABEL.get(entity_type, entity_type)
    link = f"{APP_BASE_URL}/{ENTITY_ROUTE.get(entity_type, entity_type)}/{entity_id}"
    for u in users:
        send_email(
            u.email,
            f"[ЭДО] {label} {entity_id} ожидает вашего согласования",
            f"Здравствуйте, {u.fio}!\n\n"
            f"{label} {entity_id} «{subject}» ожидает вашего решения.\n\n"
            f"Открыть: {link}\n\n— Система ЭДО Закупок",
        )


def notify_escalation(db, entity_type: str, entity_id: str, role: str, deadline_str: str):
    """Уведомляет директоров о просроченном по SLA этапе согласования."""
    from app import models
    label = ENTITY_LABEL.get(entity_type, entity_type)
    link = f"{APP_BASE_URL}/{ENTITY_ROUTE.get(entity_type, entity_type)}/{entity_id}"
    directors = db.query(models.User).filter(models.User.role == "Директор", models.User.is_active.is_(True)).all()
    for u in directors:
        send_email(
            u.email,
            f"[ЭДО] Просрочен SLA: {label} {entity_id}",
            f"Здравствуйте, {u.fio}!\n\n"
            f"{label} {entity_id} просрочен на этапе «{role}» (дедлайн был {deadline_str}).\n\n"
            f"Открыть: {link}\n\n— Система ЭДО Закупок",
        )
