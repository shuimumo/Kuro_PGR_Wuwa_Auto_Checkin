from typing import Optional

import requests
from loguru import logger
from serverchan_sdk import sc_send


class NotificationService:
    def __init__(
        self,
        bark_device_key: Optional[str] = None,
        bark_server_url: Optional[str] = None,
        server3_send_key: Optional[str] = None,
    ):
        self.bark_device_key = bark_device_key
        self.bark_server_url = bark_server_url
        self.server3_send_key = server3_send_key

    def send(self, message: str):
        title = "库街区自动签到任务"
        delivered = [
            self._send_bark(title, message),
            self._send_server3(title, message),
        ]
        if not any(delivered):
            logger.debug("No notification channel configured; skipped sending result.")

    def _send_bark(self, title: str, message: str) -> bool:
        if not self.bark_device_key or not self.bark_server_url:
            return False

        url = f"{self.bark_server_url}/{self.bark_device_key}/{title}/{message}"
        try:
            response = requests.get(url, timeout=10)
            logger.debug("Sent Bark notification, status={}", response.status_code)
        except requests.RequestException as exc:
            logger.warning("Failed to push Bark notification: {}", exc)
        return True

    def _send_server3(self, title: str, message: str) -> bool:
        if not self.server3_send_key:
            return False

        try:
            response = sc_send(
                self.server3_send_key,
                title,
                message,
                {"tags": "Kurobbs|AutoCheckin"},
            )
            logger.debug("Sent ServerChan3 notification: {}", response)
        except Exception as exc:
            logger.warning("Failed to push ServerChan3 notification: {}", exc)
        return True
