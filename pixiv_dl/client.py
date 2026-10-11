"""Pixiv 网络客户端：会话管理、Cookie、请求重试"""
import re
import time
from typing import Optional

import requests

from . import ui


class RateLimitError(Exception):
    """触发 Pixiv 限流"""


class PixivClient:
    BASE_URL = "https://www.pixiv.net"

    def __init__(self, config: dict):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.pixiv.net/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,image/apng,*/*;q=0.8,"
                      "application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        self.session.proxies.update(config.get("PROXIES", {}))
        self._setup_cookies()

    def _setup_cookies(self) -> None:
        cookie = self.config.get("COOKIE", "")
        if not cookie:
            raise ValueError("请先在 config.py 中设置 COOKIE")
        for pair in cookie.split(";"):
            if not pair.strip():
                continue
            try:
                name, value = pair.strip().split("=", 1)
                self.session.cookies.set(name, value)
            except ValueError:
                ui.warn(f"忽略无法解析的 Cookie 片段: {pair.strip()[:40]}...")

    @property
    def user_id(self) -> str:
        uid = self.config.get("USER_ID")
        if uid:
            return str(uid)
        match = re.search(r"PHPSESSID=(\d+)", self.config.get("COOKIE", ""))
        if not match:
            raise ValueError("无法从 COOKIE 中提取用户 ID，请手动设置 USER_ID")
        self.config["USER_ID"] = match.group(1)
        return match.group(1)

    def make_request(self, url: str, stream: bool = False) -> Optional[requests.Response]:
        """带指数退避重试的 GET 请求"""
        max_retries = self.config.get("MAX_RETRIES", 3)
        delay = self.config.get("RETRY_DELAY", 2)
        last_err = None

        for attempt in range(1, max_retries + 1):
            try:
                resp = self.session.get(url, stream=stream, timeout=30)
                resp.raise_for_status()
                return resp
            except Exception as e:
                last_err = e
                if "Too Many Requests" in str(e) or (
                    getattr(e, "response", None) is not None
                    and getattr(e.response, "status_code", None) == 429
                ):
                    raise RateLimitError("触发 Pixiv 请求频率限制，请稍后再试或增大 SLEEP_TIME")
                if attempt < max_retries:
                    ui.warn(f"请求失败（{attempt}/{max_retries}），{delay}s 后重试")
                    time.sleep(delay)
                    delay *= 2
        ui.error(f"请求最终失败: {last_err}")
        return None
