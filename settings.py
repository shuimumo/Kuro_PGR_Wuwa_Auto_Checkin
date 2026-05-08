from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


class SettingsError(Exception):
    """配置文件错误"""


@dataclass
class ScheduleConfig:
    time: str = "08:00"
    timezone: str = "Asia/Shanghai"


@dataclass
class NotifyConfig:
    bark_device_key: Optional[str] = None
    bark_server_url: Optional[str] = None
    server3_send_key: Optional[str] = None


@dataclass
class AccountConfig:
    token: str
    name: Optional[str] = None
    notification: Optional[NotifyConfig] = None


@dataclass
class AppConfig:
    debug: bool = False
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    notification: Optional[NotifyConfig] = None
    accounts: list = field(default_factory=list)

    @classmethod
    def load(cls, config_path: str = "config.yaml") -> "AppConfig":
        path = Path(config_path)
        if not path.is_file():
            raise SettingsError(
                f"配置文件 {config_path} 不存在，请参考 config.example.yaml 创建"
            )

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        schedule = ScheduleConfig(**data.get("schedule", {}))

        notify_data = data.get("notification") or {}
        notification = NotifyConfig(
            bark_device_key=notify_data.get("bark_device_key"),
            bark_server_url=notify_data.get("bark_server_url"),
            server3_send_key=notify_data.get("server3_send_key"),
        ) if any(notify_data.values()) else None

        accounts = []
        for item in data.get("accounts", []):
            token = (item.get("token") or "").strip()
            if not token:
                continue
            name = (item.get("name") or "").strip() or None

            acct_notify_data = item.get("notification") or {}
            acct_notification = NotifyConfig(
                bark_device_key=acct_notify_data.get("bark_device_key"),
                bark_server_url=acct_notify_data.get("bark_server_url"),
                server3_send_key=acct_notify_data.get("server3_send_key"),
            ) if any(acct_notify_data.values()) else None

            accounts.append(AccountConfig(token=token, name=name, notification=acct_notification))

        if not accounts:
            raise SettingsError(
                "配置文件中没有有效账号，请在 accounts 中添加至少一个 token"
            )

        debug = data.get("debug", False)
        return cls(debug=debug, schedule=schedule, notification=notification, accounts=accounts)
