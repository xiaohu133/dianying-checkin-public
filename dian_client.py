import os
import time
import base64
import uuid
import logging
from curl_cffi import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

logger = logging.getLogger("dian_client")

class Dian115Client:
    BASE_URL = "https://m.dian115.com"

    def __init__(self, cookie: str = "", email: str = "", password: str = ""):
        self._cookie_str = ""
        self._email = str(email or "").strip()
        self._password = str(password or "").strip()
        self._visitor_id = str(uuid.uuid4())
        self._session = requests.Session(impersonate="chrome120")
        self._private_key = ec.generate_private_key(ec.SECP256R1())
        self._browser_session_expires_at = 0.0
        self._server_time_offset_ms = 0
        self._current_proof = ""
        self._proof = None # (proof_str, expires_at)
        if cookie:
            self.set_cookie(cookie)

    @staticmethod
    def _base64url(val: bytes) -> str:
        return base64.urlsafe_b64encode(val).decode("ascii").rstrip("=")

    def _public_jwk(self) -> dict:
        nums = self._private_key.public_key().public_numbers()
        return {
            "kty": "EC",
            "crv": "P-256",
            "x": self._base64url(nums.x.to_bytes(32, "big")),
            "y": self._base64url(nums.y.to_bytes(32, "big")),
        }

    def set_credentials(self, email: str, password: str):
        self._email = str(email or "").strip()
        self._password = str(password or "").strip()

    def set_cookie(self, cookie_str: str):
        clean_cookie = str(cookie_str or "").strip()
        if clean_cookie == self._cookie_str:
            return
        self._cookie_str = clean_cookie
        self._session.cookies.clear()
        if not self._cookie_str:
            return

        if "=" in self._cookie_str:
            parts = [p.strip() for p in self._cookie_str.split(";") if p.strip()]
            for p in parts:
                if "=" in p:
                    k, v = p.split("=", 1)
                    self._session.cookies.set(k.strip(), v.strip(), domain="m.dian115.com", path="/")
        else:
            self._session.cookies.set("__Host-portal_token", self._cookie_str, domain="m.dian115.com", path="/")

    def get_cookie_string(self) -> str:
        items = []
        for k, v in self._session.cookies.items():
            items.append(f"{k}={v}")
        return "; ".join(items)

    def _headers(self, current_path: str = "/") -> dict:
        path = current_path if str(current_path).startswith("/") else "/"
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "sec-ch-ua": '"Not=A?Brand";v="99", "Google Chrome";v="130", "Chromium";v="130"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-portal-current-path": path,
            "x-portal-visitor-id": self._visitor_id,
            "x-requested-with": "XMLHttpRequest",
            "referer": f"{self.BASE_URL}{path}",
        }

    def _get_proof(self, current_path: str = "/", refresh: bool = False) -> str:
        now = time.time()
        if not refresh and self._proof and self._proof[1] > now + 15:
            return self._proof[0]

        headers = self._headers(current_path)
        r = self._session.get(f"{self.BASE_URL}/api/portal/auth/browser-challenge", headers=headers, timeout=10)
        data = r.json()
        proof = str(data.get("proof") or "")
        ttl = max(30, int(data.get("ttl") or 600))
        self._proof = (proof, now + ttl)
        self._current_proof = proof
        return proof

    def _ensure_browser_session(self, current_path: str = "/", refresh: bool = False):
        now = time.time()
        if not refresh and self._browser_session_expires_at > now + 15:
            return

        proof = self._get_proof(current_path, refresh=refresh)
        headers = self._headers(current_path)
        headers["content-type"] = "application/json"
        headers["x-portal-browser-proof"] = proof

        r = self._session.post(
            f"{self.BASE_URL}/api/portal/auth/browser-session",
            headers=headers,
            json={"public_jwk": self._public_jwk()},
            timeout=10
        )
        data = r.json()
        server_time_ms = data.get("server_time_ms")
        if server_time_ms:
            self._server_time_offset_ms = int(server_time_ms) - round(now * 1000)
        ttl = max(60, int(data.get("ttl") or 1800))
        self._browser_session_expires_at = now + ttl

    def _browser_signature(self, method: str, api_path: str) -> dict:
        ts = str(round(time.time() * 1000 + self._server_time_offset_ms))
        nonce = self._base64url(os.urandom(24))
        path = api_path.split("?")[0]
        canonical = f"portal-browser-request/v1\n{method.upper()}\n{path}\n{ts}\n{nonce}".encode("utf-8")
        der = self._private_key.sign(canonical, ec.ECDSA(hashes.SHA256()))
        r_val, s_val = decode_dss_signature(der)
        sig = self._base64url(r_val.to_bytes(32, "big") + s_val.to_bytes(32, "big"))
        return {
            "x-portal-browser-ts": ts,
            "x-portal-browser-nonce": nonce,
            "x-portal-browser-sig": sig,
        }

    def request_json(self, method: str, api_path: str, current_path: str = "/", **kwargs) -> tuple:
        self._ensure_browser_session(current_path)
        proof = self._get_proof(current_path)
        headers = self._headers(current_path)
        headers["x-portal-browser-proof"] = proof
        headers.update(self._browser_signature(method, api_path))
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        url = f"{self.BASE_URL}{api_path}"

        resp = self._session.request(method, url, headers=headers, **kwargs)

        # Handle signature / session invalid auto-recovery
        if resp.status_code in (400, 401) and any(x in resp.text for x in ["signature", "proof", "browser"]):
            logger.info("Dian115 签名或会话脱节，自动刷新重新注册 session...")
            self._browser_session_expires_at = 0
            self._proof = None
            self._ensure_browser_session(current_path, refresh=True)
            proof = self._get_proof(current_path)
            headers = self._headers(current_path)
            headers["x-portal-browser-proof"] = proof
            headers.update(self._browser_signature(method, api_path))
            resp = self._session.request(method, url, headers=headers, **kwargs)

        try:
            return resp.json(), resp.status_code
        except Exception:
            return {"error": resp.text}, resp.status_code

    def login(self, email: str = "", password: str = "") -> dict:
        """使用邮箱和密码静默登录并自动换取全新长效 Token"""
        if email: self._email = email
        if password: self._password = password
        if not self._email or not self._password:
            return {"success": False, "message": "未配置邮箱或密码"}

        logger.info("正在执行癫影静默登录刷新 Token (账号: %s)...", self._email)
        data, code = self.request_json(
            "POST",
            "/api/portal/auth/login",
            current_path="/login",
            headers={"content-type": "application/json"},
            json={"email": self._email, "password": self._password}
        )

        if code == 200 and data.get("code") == "ok":
            self._cookie_str = self.get_cookie_string()
            logger.info("癫影静默登录成功！已自动获取全新 Token")
            return {
                "success": True,
                "user": data.get("user"),
                "cookie": self._cookie_str
            }

        msg = str(data.get("msg") or data.get("message") or f"登录失败 (HTTP {code})")
        logger.error("癫影静默登录失败: %s", msg)
        return {"success": False, "message": msg}

    def get_account_info(self) -> dict:
        if not self._cookie_str and (not self._email or not self._password):
            return {"success": False, "authenticated": False, "message": "尚未配置 Cookie 或账号密码"}

        # If no cookie but email/password present, try silent login
        if not self._cookie_str and self._email and self._password:
            login_res = self.login()
            if not login_res.get("success"):
                return {"success": False, "authenticated": False, "message": login_res.get("message")}

        data, code = self.request_json("GET", "/api/portal/me", current_path="/me")

        # If token expired or unauthorized, try auto-renewal with password
        if (code == 401 or data.get("code") in ("no_token", "unauthorized")) and self._email and self._password:
            logger.warning("Token 可能已过期，尝试使用账号密码进行自动静默续期...")
            login_res = self.login()
            if login_res.get("success"):
                data, code = self.request_json("GET", "/api/portal/me", current_path="/me")

        if code == 401 or data.get("code") == "no_token":
            return {"success": False, "authenticated": False, "message": "Cookie 已失效或未登录"}

        user = data.get("user") or {}
        if not user:
            return {"success": False, "authenticated": False, "message": data.get("msg") or "无法获取用户信息"}

        return {
            "success": True,
            "authenticated": True,
            "username": user.get("nickname") or user.get("username") or user.get("email") or "癫影用户",
            "email": user.get("email", ""),
            "points": user.get("points", 0),
            "is_vip": bool(user.get("vip")),
            "vip_until": user.get("vip_until", ""),
            "consecutive_signin": user.get("consecutive_signin", 0),
            "avatar": user.get("avatar_url", ""),
            "unlock_count": data.get("unlock_count", 0),
            "last_signin_date": user.get("last_signin_date", ""),
            "cookie": self._cookie_str
        }

    def signin(self, mode: str = "lucky") -> dict:
        # Pre-check account info / auto-renew if needed
        acct = self.get_account_info()
        if not acct.get("authenticated"):
            return {
                "success": False,
                "already_checked_in": False,
                "message": acct.get("message") or "账号未登录",
                "mode": mode
            }

        mode = "lucky" if mode == "lucky" else "normal"
        headers = {"content-type": "application/json"}
        data, code = self.request_json(
            "POST",
            "/api/portal/signin",
            current_path="/me/signin",
            headers=headers,
            json={"mode": mode}
        )

        # In case of auth error during signin, try one auto-login renewal
        if (code == 401 or data.get("code") in ("no_token", "unauthorized")) and self._email and self._password:
            self.login()
            data, code = self.request_json(
                "POST",
                "/api/portal/signin",
                current_path="/me/signin",
                headers=headers,
                json={"mode": mode}
            )

        msg = str(data.get("msg") or data.get("message") or "")
        if data.get("code") == "already_signed" or "已签到" in msg:
            return {
                "success": True,
                "already_checked_in": True,
                "message": "今日已签到",
                "mode": mode,
                "award": 0,
            }
        if code == 200 and data.get("code") in ("ok", None, 0):
            return {
                "success": True,
                "already_checked_in": False,
                "message": str(data.get("message") or "签到成功"),
                "mode": mode,
                "award": data.get("award"),
                "new_balance": data.get("new_balance"),
                "streak": data.get("streak_after"),
                "lucky_tier": data.get("lucky_tier"),
                "multiplier": data.get("multiplier"),
            }
        return {
            "success": False,
            "already_checked_in": False,
            "message": msg or f"签到异常 (HTTP {code})",
            "mode": mode,
        }
