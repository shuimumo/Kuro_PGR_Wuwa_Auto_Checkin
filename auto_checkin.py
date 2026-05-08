import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests
from loguru import logger
from pydantic import BaseModel, Field


class Response(BaseModel):
    code: int = Field(..., alias="code", description="返回值")
    msg: str = Field(..., alias="msg", description="提示信息")
    success: Optional[bool] = Field(None, alias="success", description="token有时才有")
    data: Optional[Any] = Field(None, alias="data", description="请求成功才有")


class KurobbsClientException(Exception):
    """Custom exception for Kurobbs client errors."""


class KurobbsClient:
    FIND_ROLE_LIST_API_URL = "https://api.kurobbs.com/gamer/role/default"
    SIGN_URL = "https://api.kurobbs.com/encourage/signIn/v2"
    USER_SIGN_URL = "https://api.kurobbs.com/user/signIn"
    USER_MINE_URL = "https://api.kurobbs.com/user/mineV2"

    def __init__(self, token: str):
        if not token:
            raise KurobbsClientException("TOKEN is required to call Kurobbs APIs.")

        self.token = token
        self.session = requests.Session()
        self.session.headers.update(
            {
                "osversion": "Android",
                "devcode": "2fba3859fe9bfe9099f2696b8648c2c6",
                "countrycode": "CN",
                "ip": "10.0.2.233",
                "model": "2211133C",
                "source": "android",
                "lang": "zh-Hans",
                "version": "1.0.9",
                "versioncode": "1090",
                "token": self.token,
                "content-type": "application/x-www-form-urlencoded; charset=utf-8",
                "accept-encoding": "gzip",
                "user-agent": "okhttp/3.10.0",
            }
        )
        self.result: Dict[str, str] = {}
        self.exceptions: List[Exception] = []

    def _post(self, url: str, data: Dict[str, Any]) -> Response:
        """Make a POST request to the specified URL with the given data."""
        logger.debug("POST {} data={}", url, data)
        try:
            response = self.session.post(url, data=data, timeout=15)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("HTTP 请求失败: url={}, error={}", url, exc)
            raise KurobbsClientException(f"Request to {url} failed: {exc}") from exc

        try:
            res = Response.model_validate_json(response.content)
        except Exception as exc:  # noqa: BLE001
            raise KurobbsClientException(f"Failed to parse response from {url}") from exc

        logger.debug(
            "POST {} -> code={}, success={}, msg={}",
            url,
            res.code,
            res.success,
            res.msg,
        )
        return res

    def get_mine_info(self, type: int = 1) -> Dict[str, Any]:
        """Get mine info."""
        res = self._post(self.USER_MINE_URL, {"type": type})
        if not res.data:
            raise KurobbsClientException("User info is missing in response.")
        return res.data

    def get_user_game_list(self, user_id: int) -> Dict[str, Any]:
        """Get the list of games for the user."""
        res = self._post(self.FIND_ROLE_LIST_API_URL, {"queryUserId": user_id})
        if not res.data:
            raise KurobbsClientException("User game list is missing in response.")
        return res.data

    def checkin_all_games(self) -> None:
        """Perform game check-in for all bound games (战双, 鸣潮, etc.)."""
        mine_info = self.get_mine_info()
        user_id = mine_info.get("mine", {}).get("userId", 0)
        logger.info("获取到 userId={}", user_id)

        user_game_list = self.get_user_game_list(user_id=user_id)

        beijing_tz = ZoneInfo("Asia/Shanghai")
        beijing_time = datetime.now(beijing_tz)

        role_list = user_game_list.get("defaultRoleList") or []
        if not role_list:
            raise KurobbsClientException("No default role found for the user.")

        game_names = {2: "战双", 3: "鸣潮"}
        game_ids = set(r.get("gameId") for r in role_list)
        game_labels = [game_names.get(gid, f"游戏({gid})") for gid in game_ids]
        logger.info("找到 {} 个角色，涉及游戏: {}", len(role_list), game_labels)

        seen_game_ids = set()
        for role_info in role_list:
            game_id = role_info.get("gameId")
            if game_id in seen_game_ids:
                continue
            seen_game_ids.add(game_id)

            data = {
                "gameId": game_id,
                "serverId": role_info.get("serverId"),
                "roleId": role_info.get("roleId", 0),
                "userId": role_info.get("userId", 0),
                "reqMonth": f"{beijing_time.month:02d}",
            }
            resp = self._post(self.SIGN_URL, data)
            game_name = game_names.get(game_id, f"游戏(gameId={game_id})")
            if resp.success:
                self.result[f"checkin_{game_id}"] = f"{game_name}签到成功"
                logger.info("{} -> {}", game_name, "签到成功")
            else:
                self.exceptions.append(KurobbsClientException(f"{game_name}签到失败, {resp.msg}"))

    def sign_in(self) -> Response:
        """Perform the sign-in operation."""
        return self._post(self.USER_SIGN_URL, {"gameId": 2})

    def _process_sign_action(
        self,
        action_name: str,
        action_method: Callable[[], Response],
        success_message: str,
        failure_message: str,
    ):
        """Handle the common logic for sign-in actions."""
        resp = action_method()
        if resp.success:
            self.result[action_name] = success_message
            logger.info("{} -> {}", action_name, success_message)
        else:
            self.exceptions.append(KurobbsClientException(f"{failure_message}, {resp.msg}"))

    def start(self):
        """Start the sign-in process."""
        logger.info("开始执行游戏签到...")
        self.checkin_all_games()

        logger.info("开始执行社区签到...")
        self._process_sign_action(
            action_name="sign_in",
            action_method=self.sign_in,
            success_message="社区签到成功",
            failure_message="社区签到失败",
        )

        self._log()

    @property
    def msg(self) -> str:
        return "\n".join(self.result.values()) if self.result else ""

    def _log(self):
        """Log the results and raise exceptions if any."""
        if msg := self.msg:
            logger.info(msg)
        if self.exceptions:
            raise KurobbsClientException("\n".join(map(str, self.exceptions)))


def run_account(token: str, name: Optional[str] = None, max_retries: int = 3):
    """Run checkin for a single account. Returns (label, lines).
    失败时自动重试（非重复签到类错误），最多重试 max_retries 次（总共 1+max_retries 次）。
    """
    label = name or "未知"
    last_error: Optional[Exception] = None
    actual_retries = 0

    for attempt in range(max_retries + 1):
        try:
            kurobbs = KurobbsClient(token)
            kurobbs.start()
            if kurobbs.msg:
                if attempt > 0:
                    logger.info("账号 {} 第{}次重试成功", label, attempt)
                return (name, kurobbs.msg.split("\n"))
            return (name, [])
        except KurobbsClientException as e:
            last_error = e
            error_msg = str(e)

            # 重复签到说明今日已签，无需重试也无需报错
            if "请勿重复签到" in error_msg:
                logger.info("账号 {} 今日已签到，跳过", label)
                return (name, error_msg.split("\n"))

            if attempt < max_retries:
                actual_retries += 1
                delay = 5 * (2 ** attempt)  # 5, 10, 20 秒退避
                logger.warning(
                    "账号 {} 签到失败(第{}/{}次)，{}秒后重试: {}",
                    label, attempt + 1, max_retries + 1, delay, error_msg,
                )
                time.sleep(delay)
        except Exception as e:
            logger.exception("An unexpected error occurred: {}", e)
            return (name, [f"未知错误: {e}"])

    logger.error("账号 {} 签到最终失败（已重试{}次）: {}", label, actual_retries, str(last_error))
    return (name, str(last_error).split("\n"))
