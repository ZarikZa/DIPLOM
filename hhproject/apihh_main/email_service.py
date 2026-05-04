from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from .models import Company


def _resolve_from_email() -> str | None:
    return (
        getattr(settings, "DEFAULT_FROM_EMAIL", "")
        or getattr(settings, "SERVER_EMAIL", "")
        or getattr(settings, "EMAIL_HOST_USER", "")
        or None
    )


def send_email_message(
    *,
    recipient_email: str,
    subject: str,
    plain_message: str,
    html_message: str | None = None,
    fail_silently: bool = False,
) -> bool:
    recipient = (recipient_email or "").strip()
    if not recipient:
        return False

    message = EmailMultiAlternatives(
        subject=subject,
        body=plain_message,
        from_email=_resolve_from_email(),
        to=[recipient],
    )
    if html_message:
        message.attach_alternative(html_message, "text/html")

    message.send(fail_silently=fail_silently)
    return True


def send_company_status_email(
    *,
    recipient_email: str,
    company_name: str,
    new_status: str,
    old_status: str | None = None,
    admin_notes: str = "",
) -> bool:
    status_title_map = {
        Company.STATUS_APPROVED: "Компания подтверждена",
        Company.STATUS_REJECTED: "Компания отклонена",
        Company.STATUS_PENDING: "Компания на проверке",
    }
    status_desc_map = {
        Company.STATUS_APPROVED: "Ваша компания прошла модерацию и теперь может работать на платформе.",
        Company.STATUS_REJECTED: "Компания не прошла модерацию. Проверьте данные и документы.",
        Company.STATUS_PENDING: "Компания находится на проверке. Ожидайте решение администратора.",
    }
    status_display_map = dict(Company.STATUS_CHOICES)

    new_status_display = status_display_map.get(new_status, new_status or "неизвестно")
    old_status_display = status_display_map.get(old_status, old_status or "—")
    title = status_title_map.get(new_status, "Статус компании обновлен")
    description = status_desc_map.get(new_status, f"Новый статус компании: {new_status_display}")

    note_text = (admin_notes or "").strip()
    note_line = f"\nКомментарий администратора: {note_text}\n" if note_text else ""
    note_html = (
        f"<p style=\"margin:0 0 14px 0;\"><b>Комментарий администратора:</b> {note_text}</p>"
        if note_text
        else ""
    )

    subject = f'WorkMPT: обновлен статус компании "{company_name}"'
    plain_message = (
        f"Здравствуйте!\n\n"
        f'Статус компании "{company_name}" изменен.\n'
        f"Старый статус: {old_status_display}\n"
        f"Новый статус: {new_status_display}\n"
        f"{note_line}"
        f"{description}\n\n"
        f"Это автоматическое сообщение WorkMPT."
    )
    html_message = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:Arial,sans-serif;background:#f8fafc;color:#1f2937;">
      <div style="max-width:640px;margin:24px auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;padding:24px;">
        <h2 style="margin:0 0 12px 0;color:#1d4ed8;">{title}</h2>
        <p style="margin:0 0 14px 0;">Здравствуйте! Статус компании <b>{company_name}</b> обновлен.</p>
        <p style="margin:0 0 8px 0;"><b>Старый статус:</b> {old_status_display}</p>
        <p style="margin:0 0 8px 0;"><b>Новый статус:</b> {new_status_display}</p>
        {note_html}
        <p style="margin:0;">{description}</p>
      </div>
    </body>
    </html>
    """

    return send_email_message(
        recipient_email=recipient_email,
        subject=subject,
        plain_message=plain_message,
        html_message=html_message,
        fail_silently=False,
    )
