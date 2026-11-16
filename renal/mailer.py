"""Envío opcional del resultado público por correo. No guarda direcciones."""
from dataclasses import dataclass
from email.message import EmailMessage
import re
import smtplib
import ssl
from urllib.parse import quote

EMAIL_RE = re.compile(r"^[^@\s<>,;\"']{1,64}@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
SUBJECT = "Tu índice TyG · Semáforo Renal"
MAX_SENDS_PER_SESSION = 3


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    sender: str

    @classmethod
    def from_settings(cls, get):
        """Devuelve la configuración solo si están todos los datos necesarios."""
        host, user, password = get("RENAL_SMTP_HOST"), get("RENAL_SMTP_USER"), get("RENAL_SMTP_PASSWORD")
        if not (host and user and password):
            return None
        try:
            port = int(get("RENAL_SMTP_PORT") or 587)
        except ValueError:
            return None
        return cls(host, port, user, password, get("RENAL_SMTP_FROM") or user)


def valid_email(address):
    address = (address or "").strip()
    return len(address) <= 254 and bool(EMAIL_RE.match(address))


def mailto_link(address, body):
    """Enlace que abre la app de correo de la persona con el resultado ya escrito."""
    to = quote(address.strip()) if valid_email(address) else ""
    return f"mailto:{to}?subject={quote(SUBJECT)}&body={quote(body)}"


def send_result(config, address, body, timeout=15):
    if not valid_email(address):
        raise ValueError("Escribe un correo válido, por ejemplo nombre@correo.com.")
    message = EmailMessage()
    message["Subject"] = SUBJECT
    message["From"] = config.sender
    message["To"] = address.strip()
    message.set_content(body)
    context = ssl.create_default_context()
    if config.port == 465:
        with smtplib.SMTP_SSL(config.host, config.port, timeout=timeout, context=context) as server:
            server.login(config.user, config.password)
            server.send_message(message)
    else:
        with smtplib.SMTP(config.host, config.port, timeout=timeout) as server:
            server.starttls(context=context)
            server.login(config.user, config.password)
            server.send_message(message)
