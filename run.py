import sys
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

import schedule
from loguru import logger

from auto_checkin import run_account
from ext_notification import NotificationService
from logging_utils import configure_logger
from settings import AppConfig, SettingsError


# 防止同一天内重复签到
_last_checkin_date: str | None = None


def collect_secrets(config: AppConfig) -> list:
    """收集所有账号中的敏感信息，用于日志脱敏"""
    secrets = []
    for acct in config.accounts:
        secrets.append(acct.token)
        if acct.notification:
            secrets.extend([
                acct.notification.bark_device_key or "",
                acct.notification.bark_server_url or "",
                acct.notification.server3_send_key or "",
            ])
    if config.notification:
        secrets.extend([
            config.notification.bark_device_key or "",
            config.notification.bark_server_url or "",
            config.notification.server3_send_key or "",
        ])
    return [s for s in secrets if s]


def convert_schedule_time(time_str: str, source_tz: str) -> str:
    """将指定时区的时间转换为本地时区 HH:MM"""
    try:
        source_zone = ZoneInfo(source_tz)
        hour, minute = map(int, time_str.split(":"))
        source_now = datetime.now(source_zone)
        source_target = source_now.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        local_target = source_target.astimezone()
        local_time = f"{local_target.hour:02d}:{local_target.minute:02d}"
        logger.info(
            "时区转换: {} {} -> 本地时间 {} (系统时区: {})",
            time_str, source_tz, local_time, local_target.tzinfo,
        )
        return local_time
    except Exception:
        logger.warning("时区转换失败，使用原始时间 {}", time_str)
        return time_str


def run_all_accounts(config: AppConfig):
    """遍历所有账号执行签到，全局通知汇总所有账号，单账号有独立通知配置的额外单独发送"""
    global _last_checkin_date

    today = date.today().isoformat()
    if _last_checkin_date == today:
        logger.info("今日已完成签到，跳过重复执行")
        return
    _last_checkin_date = today

    logger.info("========== 开始执行签到任务 ==========")
    account_results = []

    for i, account in enumerate(config.accounts):
        logger.info("--- 账号 {}/{} ---", i + 1, len(config.accounts))
        label = account.name or f"账号{i + 1}"
        try:
            _, lines = run_account(token=account.token, name=account.name)
        except Exception as e:
            logger.error("账号 {} 签到异常: {}", label, e)
            lines = [f"执行异常: {e}"]
        account_results.append((label, account, lines))

    logger.info("========== 签到任务执行完毕 ==========")

    # 构建全局汇总消息
    combined_lines = []
    for label, _account, lines in account_results:
        combined_lines.append(f"【{label}】")
        combined_lines.extend(lines)
        combined_lines.append("")
    combined_message = "\n".join(combined_lines).strip()

    # 全局通知：汇总所有账号结果，使用全局token发送一次
    if config.notification:
        notifier = NotificationService(
            bark_device_key=config.notification.bark_device_key,
            bark_server_url=config.notification.bark_server_url,
            server3_send_key=config.notification.server3_send_key,
        )
        notifier.send(combined_message)

    # 单账号通知：给配置了独立通知token的账号单独发一条
    for label, account, lines in account_results:
        if account.notification:
            acct_message = "\n".join([f"【{label}】"] + lines)
            acct_notifier = NotificationService(
                bark_device_key=account.notification.bark_device_key,
                bark_server_url=account.notification.bark_server_url,
                server3_send_key=account.notification.server3_send_key,
            )
            acct_notifier.send(acct_message)

    # 统计执行结果
    total = len(account_results)
    success = sum(1 for _, _, lines in account_results if not lines or all(
        "签到成功" in l or "已签到" in l for l in lines
    ))
    logger.info("签到汇总: {}/{} 个账号成功", success, total)

    has_any_notification = config.notification is not None or any(
        acct.notification for _, acct, _ in account_results
    )
    if not has_any_notification and not combined_message:
        logger.debug("无签到结果")


def main():
    try:
        config = AppConfig.load()
    except SettingsError as e:
        logger.error(str(e))
        sys.exit(1)

    configure_logger(debug=config.debug, secrets=collect_secrets(config))

    # 启动时立即执行一次
    run_all_accounts(config)

    # 设置每日定时任务
    local_time = convert_schedule_time(
        config.schedule.time, config.schedule.timezone
    )
    schedule.every().day.at(local_time).do(run_all_accounts, config)

    logger.info(
        "定时任务已设置: 每天 {} ({}) 执行签到，本地时间 {}",
        config.schedule.time,
        config.schedule.timezone,
        local_time,
    )

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("签到服务已停止")


if __name__ == "__main__":
    main()
