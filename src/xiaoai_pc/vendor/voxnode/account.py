"""小米账号登录（同步版）。

登录流程参考 Yonsm/MiService（MIT，© 2021-2026 Yonsm）的公开实现，以其协议为准：
1. GET  /pass/serviceLogin?sid=...  获取 qs / _sign / callback
2. POST /pass/serviceLoginAuth2     提交账号 + MD5(密码)
3. GET  location&clientSign=...     换取 serviceToken
支持 OTP（短信/邮箱验证码）与 passToken 会话续期。
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import string
import threading
import time
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote, urlparse, parse_qs

import requests

ACCOUNT_BASE = "https://account.xiaomi.com"
JSON_PREFIX = "&&&START&&&"

UA_LOGIN = (
    "APP/com.xiaomi.mihome APPV/11.3.203 iosPassportSDK/4.2.50 iOS/26.3.1 "
    "MK/aVBob25lMTcsMg== DEVT/aVBob25l DEVS/aU9T BRA/QXBwbGU= L/zh_CN"
)
UA_OTP = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 MiHome/11.3.203"
)
UA_MINA = "MiHome/6.0.103 (com.xiaomi.mihome; build:6.0.103.1; iOS 14.4.0) Alamofire/6.0.103 MICO/iOSApp/appStore/6.0.103"
UA_MIIO = (
    "iOS-14.4-6.0.103-iPhone12,3--D7744744F7AF32F0544445285880DD63E47D9BE9-"
    "8816080-84A3F44E137B71AE-iPhone"
)

SID_MINA = "micoapi"      # MiNA（小爱音箱）服务 id
SID_MIIO = "xiaomiio"     # 米家 / MIoT 设备云服务 id
SID_MIJIA = "mijia"       # 米家 App 体系（扫码登录可选）


class XiaomiAuthError(Exception):
    pass


class XiaomiServiceError(Exception):
    pass


def _rand(length: int) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def _parse_resp(raw: str) -> dict:
    if raw.startswith(JSON_PREFIX):
        raw = raw[len(JSON_PREFIX):]
    try:
        result = json.loads(raw) if raw.strip() else {}
        if not isinstance(result, dict):
            raise ValueError
        return result
    except ValueError:
        raise XiaomiAuthError("小米账号接口返回了无法解析的内容") from None


class MiAccount:
    """管理小米账号登录、serviceToken 缓存与带会话的 API 请求（线程安全）。"""

    def __init__(self, username: str, password: str,
                 token_path: Optional[Path] = None,
                 otp_callback: Optional[Callable[[str], str]] = None):
        self.username = username
        self.password = password
        self.token_path = Path(token_path) if token_path else None
        self.otp_callback = otp_callback
        self.token: dict = {}
        self._lock = threading.RLock()
        self._session = requests.Session()
        self._load_token()

    # -- token 持久化 --------------------------------------------------
    def _load_token(self) -> None:
        if self.token_path:
            raise ValueError("明文令牌缓存已禁用，请使用 SecureAccount")

    def _save_token(self, token: Optional[dict] = None) -> None:
        if self.token_path:
            raise ValueError("明文令牌缓存已禁用，请使用 SecureAccount")

    # -- 登录 ----------------------------------------------------------
    def login(self, sid: str = SID_MINA) -> bool:
        """登录并缓存 serviceToken。需要验证码时通过 otp_callback 获取。"""
        with self._lock:
            if not self.password and not self.token.get("passToken"):
                raise XiaomiAuthError("未保存密码，请使用「扫码登录」或重新输入账号密码")
            if not self.token.get("deviceId"):
                self.token["deviceId"] = _rand(16).upper()
            try:
                resp = self._service_login(f"serviceLogin?sid={sid}&_json=true")
                if resp.get("code") != 0:
                    if not self.password:
                        raise XiaomiAuthError("小米登录已过期，请重新扫码登录")
                    data = {
                        "_json": "true",
                        "qs": resp["qs"],
                        "sid": resp["sid"],
                        "_sign": resp["_sign"],
                        "callback": resp["callback"],
                        "user": self.username,
                        "hash": hashlib.md5(self.password.encode()).hexdigest().upper(),
                    }
                    resp = self._service_login("serviceLoginAuth2", data)
                    if resp.get("code") != 0:
                        raise XiaomiAuthError("账号登录失败，请核对账号或使用扫码登录")
                    if ntf := resp.get("notificationUrl"):
                        resp = self._verify_otp(sid, ntf)
                for key in ("userId", "passToken", "location", "nonce", "ssecurity"):
                    if key not in resp:
                        raise XiaomiAuthError(f"登录响应缺少必要字段 {key}")
                self.token["userId"] = resp["userId"]
                self.token["passToken"] = resp["passToken"]
                service_token = self._security_token_service(resp["location"], resp["nonce"], resp["ssecurity"])
                self.token[sid] = [resp["ssecurity"], service_token]
                self._save_token(self.token)
                return True
            except Exception:
                # Do not destroy passToken on a temporary network failure.
                raise

    def login_with_pass_token(self, sid: str, pass_token: str, user_id: str,
                              device_id: str = "") -> bool:
        """用 passToken 换取指定 sid 的 serviceToken。

        扫码登录只会拿到一次 passToken，之后可用它免扫码换取各业务
        sid（micoapi / xiaomiio）的独立令牌。
        """
        with self._lock:
            if device_id:
                self.token["deviceId"] = device_id
            self.token.setdefault("deviceId", _rand(16).upper())
            self.token["userId"] = user_id
            self.token["passToken"] = pass_token
            resp = self._service_login(f"serviceLogin?sid={sid}&_json=true")
            if resp.get("code") != 0:
                raise XiaomiAuthError("小米登录凭据换取失败，请重新登录")
            for key in ("location", "nonce", "ssecurity"):
                if key not in resp:
                    raise XiaomiAuthError(f"换取令牌响应缺少必要字段 {key}")
            service_token = self._security_token_service(
                resp["location"], resp["nonce"], resp["ssecurity"])
            self.token["userId"] = resp.get("userId", user_id)
            self.token["passToken"] = resp.get("passToken", pass_token)
            self.token[sid] = [resp["ssecurity"], service_token]
            self._save_token(self.token)
            return True

    def _service_login(self, uri: str, data: Optional[dict] = None) -> dict:
        headers = {"User-Agent": UA_LOGIN}
        cookies = {"sdkVersion": "3.9", "deviceId": self.token["deviceId"]}
        if "passToken" in self.token:
            cookies["userId"] = str(self.token["userId"])
            cookies["passToken"] = self.token["passToken"]
        url = f"{ACCOUNT_BASE}/pass/{uri}"
        if data is None:
            r = self._session.get(url, cookies=cookies, headers=headers, timeout=30)
        else:
            r = self._session.post(url, data=data, cookies=cookies, headers=headers, timeout=30)
        r.raise_for_status()
        return _parse_resp(r.text)

    def _security_token_service(self, location: str, nonce: str, ssecurity: str) -> str:
        client_sign = hashlib.sha1(f"nonce={nonce}&{ssecurity}".encode()).digest()
        import base64
        sign = quote(base64.b64encode(client_sign).decode())
        r = self._session.get(f"{location}&clientSign={sign}", timeout=30)
        service_token = r.cookies.get("serviceToken")
        if not service_token:
            raise XiaomiAuthError("获取小米业务令牌失败")
        return service_token

    def _verify_otp(self, sid: str, ntf: str) -> dict:
        """OTP 两步验证（短信优先）。"""
        if not self.otp_callback:
            raise XiaomiAuthError("需要短信/邮箱验证码，但未提供输入回调")
        if not ntf.startswith("http"):
            ntf = ACCOUNT_BASE + ntf
        headers = {"User-Agent": UA_OTP}
        cookies = {"deviceId": self.token["deviceId"]}
        self._session.get(ntf, cookies=cookies, headers=headers, timeout=30)

        qs = parse_qs(urlparse(ntf).query)
        context = qs.get("context", [""])[0]
        sid_param = qs.get("sid", [sid])[0]
        list_url = f"{ACCOUNT_BASE}/identity/list?sid={sid_param}&supportedMask=0&_locale=zh_CN&context={context}"
        idata = _parse_resp(self._session.get(list_url, cookies=cookies, headers=headers, timeout=30).text)
        flag = idata.get("flag", 4)
        method = "Email" if flag == 8 else "Phone"

        tresp = _parse_resp(self._session.get(
            f"{ACCOUNT_BASE}/identity/auth/verify{method}?_flag={flag}&_json=true",
            cookies=cookies, headers=headers, timeout=30).text)
        if tresp.get("code") not in (0, None):
            raise XiaomiAuthError("触发验证码失败")
        if method == "Phone":
            sresp = _parse_resp(self._session.post(
                f"{ACCOUNT_BASE}/identity/auth/sendPhoneTicket",
                data={"retry": "0", "icode": "", "_json": "true"},
                cookies=cookies, headers=headers, timeout=30).text)
            if sresp.get("code") not in (0, None):
                raise XiaomiAuthError("发送短信验证码失败")

        code = (self.otp_callback(method) or "").strip()
        if not code:
            raise XiaomiAuthError("未提供验证码")
        vresp = _parse_resp(self._session.post(
            f"{ACCOUNT_BASE}/identity/auth/verify{method}?_dc={int(time.time() * 1000)}",
            data={"_flag": str(flag), "ticket": code, "trust": "false", "_json": "true"},
            cookies=cookies, headers=headers, timeout=30).text)
        location = vresp.get("location")
        if not location:
            raise XiaomiAuthError("验证码校验失败")
        if not location.startswith("http"):
            location = ACCOUNT_BASE + location
        self._session.get(location, cookies=cookies, headers=headers, timeout=30)
        resp = self._service_login(f"serviceLogin?sid={sid}&_json=true")
        if resp.get("code") == 0:
            return resp
        raise XiaomiAuthError("验证码验证后登录恢复失败")

    # -- 业务请求 ------------------------------------------------------
    def is_logged_in(self, sid: str = SID_MINA) -> bool:
        return bool(self.token.get(sid)) and bool(self.token.get("userId"))

    def auth_cookies(self, sid: str) -> dict:
        """确保该 sid 已登录，返回带 serviceToken 的 cookie。"""
        if not self.is_logged_in(sid) and not self.login(sid):
            raise XiaomiAuthError(f"登录失败 (sid={sid})")
        return {
            "userId": str(self.token["userId"]),
            "serviceToken": self.token[sid][1],
        }

    def raw_request(self, sid: str, url: str, data=None, headers: Optional[dict] = None,
                    sign=None, relogin: bool = True) -> dict:
        """底层请求，返回原始 JSON（不校验 code 字段）。

        sign 可为 ``callable(data, token, cookies, headers) -> content``，
        用于 MiIO / MIoT 这类需要 HMAC 签名并补充 cookie、header 的接口。
        """
        with self._lock:
            cookies = self.auth_cookies(sid)
            hdrs = {"User-Agent": UA_MINA}
            if headers:
                hdrs.update(headers)
            content = data
            if callable(sign):
                content = sign(data, self.token, cookies, hdrs)
            method = "GET" if content is None else "POST"
            r = self._session.request(method, url, data=content, cookies=cookies,
                                      headers=hdrs, timeout=30)
            if r.status_code == 401 and relogin:
                self.token.pop(sid, None)
                self._session.cookies.clear()
                return self.raw_request(sid, url, data, headers, sign, relogin=False)
            if r.status_code in (401, 403):
                raise XiaomiAuthError("小米授权失效，请重新登录")
            r.raise_for_status()
            try:
                result = r.json()
                if not isinstance(result, dict):
                    raise ValueError
                return result
            except ValueError:
                raise XiaomiServiceError("小米接口响应结构不正确") from None

    def request(self, url: str, data=None, headers: Optional[dict] = None,
                relogin: bool = True, sid: str = SID_MINA) -> dict:
        """MiNA 风格请求：要求 code == 0，否则抛出异常。"""
        resp = self.raw_request(sid, url, data, headers, relogin=relogin)
        if resp.get("code", -1) == 0:
            return resp
        if "auth" in str(resp.get("message", "")).lower():
            if relogin:
                self.token.pop(sid, None)
                self._session.cookies.clear()
                return self.request(url, data, headers, relogin=False, sid=sid)
            raise XiaomiAuthError("小米授权失效，请重新登录")
        raise XiaomiServiceError("小米业务接口返回错误，请检查账号和设备状态")


def logout(token_path: Path) -> None:
    MiAccount("", "", token_path=token_path)._save_token()
