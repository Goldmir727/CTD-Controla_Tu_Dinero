"""Códigos por correo con estilo CTD (navy + mint) y formato que Gmail detecta.

Para que Gmail ofrezca copiar/pegar el código: asunto con "código de
verificación" y el código en texto plano, solo, en su propia línea.
El HTML lo muestra grande con letter-spacing (el copiado sigue contiguo).
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

log = logging.getLogger("ctd.email")


def _html(titulo: str, intro: str, code: str, nota: str) -> str:
    return f"""<html><body style="margin:0;padding:0;background:#F7F9FA;font-family:Arial,Helvetica,sans-serif;">
<div style="max-width:480px;margin:0 auto;padding:24px 16px;">
<div style="background:#050B3B;border-radius:16px 16px 0 0;padding:20px;text-align:center;">
<span style="color:#00FFAB;font-weight:bold;letter-spacing:2px;font-size:13px;">CTD · CONTROLA TU DINERO</span>
</div>
<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-top:0;border-radius:0 0 16px 16px;padding:28px 24px;text-align:center;">
<p style="color:#10202F;font-size:16px;margin:0 0 4px;"><strong>{titulo}</strong></p>
<p style="color:#6B7A87;font-size:14px;margin:0 0 20px;">{intro}</p>
<div style="font-size:34px;font-weight:bold;letter-spacing:10px;color:#050B3B;background:#F7F9FA;border:1px dashed #8CA0B8;border-radius:12px;padding:14px 8px 14px 18px;margin:0 0 20px;">{code}</div>
<p style="color:#6B7A87;font-size:13px;margin:0;">{nota}</p>
</div>
<p style="color:#8CA0B8;font-size:12px;text-align:center;margin:16px 0 0;">CTD · Tus datos. Tus decisiones.</p>
</div>
</body></html>"""


def _send(to_email: str, subject: str, text: str, html: str, dev_tag: str, code: str) -> None:
    if not settings.smtp_host or not settings.smtp_user:
        log.warning("SMTP no configurado. %s para %s: %s", dev_tag, to_email, code)
        print(f"[{dev_tag}] {to_email}: {code}")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
        s.starttls()
        s.login(settings.smtp_user, settings.smtp_password)
        s.send_message(msg)


def send_2fa_code(to_email: str, code: str) -> None:
    ttl = settings.twofa_ttl_min
    text = (
        f"Se solicitó un código de verificación para entrar a CTD.\n\n{code}\n\n"
        f"Vence en {ttl} minutos. Si no lo pediste, ignóralo."
    )
    html = _html(
        "Se solicitó un código de verificación",
        "Úsalo para entrar a CTD. Si no lo pediste, ignora este correo.",
        code,
        f"Vence en {ttl} minutos.",
    )
    _send(to_email, "[CTD] Código de verificación para entrar", text, html, "2FA DEV", code)


def send_password_code(to_email: str, code: str) -> None:
    ttl = settings.twofa_ttl_min
    text = (
        f"Se solicitó un código de verificación para cambiar tu contraseña de CTD.\n\n{code}\n\n"
        f"Vence en {ttl} minutos. Si no lo pediste, ignóralo y revisa tu cuenta."
    )
    html = _html(
        "Se solicitó un código de verificación",
        "Úsalo para cambiar tu contraseña de CTD. Si no lo pediste, revisa tu cuenta.",
        code,
        f"Vence en {ttl} minutos.",
    )
    _send(to_email, "[CTD] Código de verificación para tu contraseña", text, html, "PW DEV", code)
