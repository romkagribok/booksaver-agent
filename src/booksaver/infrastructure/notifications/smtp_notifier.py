from __future__ import annotations

import smtplib
from email.message import EmailMessage


class SmtpEmailNotifier:
    """Notifier adapter over stdlib smtplib with STARTTLS (ADR-011)."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        recipient: str,
        timeout: float = 30.0,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._recipient = recipient
        self._timeout = timeout

    @property
    def channel_name(self) -> str:
        return "email"

    def send(self, subject: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self._username
        message["To"] = self._recipient
        message.set_content(body)

        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
            smtp.starttls()
            smtp.login(self._username, self._password)
            smtp.send_message(message)
