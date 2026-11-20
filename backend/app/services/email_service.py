import smtplib
from email.message import EmailMessage
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.config.settings import Settings


class PasswordResetEmailService:
    def __init__(self, settings: Settings):
        required = (
            settings.smtp_host,
            settings.smtp_sender,
            settings.password_reset_url,
        )
        if not all(required):
            raise RuntimeError("SMTP_HOST, SMTP_SENDER and PASSWORD_RESET_URL are required")
        if settings.smtp_username and not settings.smtp_password:
            raise RuntimeError("SMTP_PASSWORD is required when SMTP_USERNAME is set")

        self.settings = settings

    def send_password_reset(self, email: str, token: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Redefinição de senha do NutriIA"
        message["From"] = self.settings.smtp_sender
        message["To"] = email
        message.set_content(
            "Use o link abaixo para redefinir sua senha. Ele expira em "
            f"{self.settings.password_reset_token_expire_minutes} minutos e só pode ser usado uma vez.\n\n"
            f"{self._reset_link(token)}\n\n"
            "Se você não solicitou a redefinição, ignore este e-mail."
        )

        if self.settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as smtp:
                self._authenticate(smtp)
                smtp.send_message(message)
            return

        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            self._authenticate(smtp)
            smtp.send_message(message)

    def _authenticate(self, smtp: smtplib.SMTP | smtplib.SMTP_SSL) -> None:
        if self.settings.smtp_username:
            smtp.login(self.settings.smtp_username, self.settings.smtp_password)

    def _reset_link(self, token: str) -> str:
        parts = urlsplit(self.settings.password_reset_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["token"] = token
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
